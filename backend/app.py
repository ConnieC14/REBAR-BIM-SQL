# FASTAPI
"""
Backend for the REBAR UI. Each answer runs an evaluated variant's pipeline
(same database, retrieval, step limit and read-only guard as the eval runs).
Run from backend/:

    uvicorn app:app --port 8000

Endpoints:
    GET  /               health check and the available models
    GET  /schema         tables, columns and foreign keys (for the table map)
    GET  /examples       checked example questions, with the tables each one needs
    POST /query/stream   {"question", "model", "compare"} -> server-sent events, one
                         per agent step, then a "done" event per lane

Models are listed in app_models.yaml. Paid models stop at APP_MAX_USD per lane.
"""
import os
import json
import queue
import threading
from contextlib import contextmanager
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from evals.run import ENV_PATH, load_config, apply_config_env, build_pipeline_for
from utils import tracing

load_dotenv(ENV_PATH)


def load_models(path="app_models.yaml"):
    # Lanes: "agent" answers, "baseline" runs next to it in Compare. Prompt rules are
    # fixed per pipeline at build time, the guard is read per query (both lanes).
    with open(path) as models_file:
        spec = yaml.safe_load(models_file)
    models = {}
    for entry in spec["models"]:
        key = entry.get("api_key_env")
        if key and not os.getenv(key):
            print(f"Model '{entry['id']}' hidden: {key} is not set in .env")
            continue
        llm = load_config(entry["agent"])["llm"]
        models[entry["id"]] = {**entry, "model": llm["model"], "local": llm["provider"] == "ollama"}
    return models, spec.get("default")


MODELS, default = load_models()
DEFAULT_MODEL = os.getenv("APP_MODEL") or default
if DEFAULT_MODEL not in MODELS:
    DEFAULT_MODEL = next(iter(MODELS))
MAX_USD = float(os.getenv("APP_MAX_USD", "0.05"))   # per lane, per question
EXAMPLES = [  # (group, suite item id); answers were checked in the eval runs
    ("Retrieval", "bim-hard-003"), ("Retrieval", "bim-easy-004"),
    ("Retrieval", "bim-med-016"), ("Retrieval", "bim-med-025"),
    ("Safety", "bsaf-write-001"), ("Safety", "bsaf-indirect-001"),
    ("Safety", "bsaf-direct-001"),
    ("Trick", "bsaf-unans-001"), ("Trick", "bsaf-unans-002"),
]

apply_config_env(load_config(MODELS[DEFAULT_MODEL]["agent"]))

# Pipeline modules read the environment at import time, so import after apply_config_env
from scripts.chromadb_table_column_descriptions import ChromaDBManager
from vector_db_agent_pipeline import populate_metadata
from evals.common import engine_for, load_suite
from evals.scorers import PRICES, score_cost, schema_elements
from agents.retrieval import SchemaCatalog

# Prices from app_models.yaml, for models the scorer has none for (no price, no cap)
for spec in MODELS.values():
    if spec.get("price_usd_per_mtok"):
        price_in, price_out = spec["price_usd_per_mtok"]
        PRICES.setdefault(spec["model"], (price_in, price_out, price_in))

manager = ChromaDBManager()
engines = {profile: engine_for(profile) for profile in ("default", "injected")}
populate_metadata(manager, engines["default"], "./data")
catalog = SchemaCatalog(manager, engines["default"])

pipelines = {}                     # (model, lane, profile) -> pipeline, built on first use
run_lock = threading.Lock()        # one question at a time: the model settings are process-wide


def pipeline_for(model: str, lane: str, profile: str):
    key = (model, lane, profile)
    if key not in pipelines:
        config = load_config(MODELS[model][lane])
        apply_config_env(config)
        pipelines[key] = build_pipeline_for(config)(manager, engines[profile])
    return pipelines[key]


def use_model(model: str):
    """
    Sets the model's settings (LLM, step limit, guard) for the next run.
    """
    apply_config_env(load_config(MODELS[model]["agent"]))


def table_names(sql: str) -> list:
    tables = schema_elements(sql, "sqlite")[0] or []
    return sorted({catalog.resolve(t) for t in tables if catalog.resolve(t)})


def client_event(kind: str, data: dict):
    """
    The part of a trace event the UI shows, or None.
    """
    if kind == "tool_call":
        return {"type": "step", "tool": data["name"], "input": data["input"][:300]}
    if kind == "schema_search":
        return {"type": "tables_seen", "tables": list(data["tables"])}
    if kind == "value_search":
        hits = list(data["hits"])
        return {"type": "values", "hits": hits[:5], "count": len(hits)}
    if kind == "retrieval":
        return {"type": "tables_given", "tables": sorted({i["table"] for i in data["items"] if i.get("table")})}
    if kind == "sql":
        return {"type": "sql", "sql": data["sql"], "ok": bool(data["ok"]), "rows": data.get("row_count"),
                "truncated": bool(data.get("truncated")), "error": (data.get("error") or "")[:200] or None,
                "blocked": bool(data.get("blocked")), "columns": list(data.get("columns") or []),
                "sample": [list(r) for r in (data.get("rows") or [])[:5]], "tables": table_names(data["sql"])}
    if kind == "tool_result" and data["name"].lower().replace(" ", "_") in ("describe_table", "find_join_path"):
        lines = [line.strip() for line in str(data["output"]).splitlines() if line.strip()]
        return {"type": "note", "text": " ".join(lines[:2])[:200]}
    if kind == "llm_call":
        return {"type": "thinking"}
    return None


class CostCapExceeded(RuntimeError):
    pass


class StreamTrace(tracing.Trace):
    """
    A trace that also sends each event to the UI as it is recorded.
    """

    def __init__(self, lane, question, send):
        super().__init__(lane, question)
        self.lane, self.send = lane, send

    def add(self, kind, **data):
        super().add(kind, **data)
        event = client_event(kind, data)
        if event:
            self.send({"lane": self.lane, "t": self.events[-1]["t"], **event})
        if kind == "llm_call" and score_cost({"events": self.events})["cost_usd"] > MAX_USD:
            raise CostCapExceeded(f"Stopped: this question passed the ${MAX_USD:.2f} cost cap.")


@contextmanager
def active(trace):
    token = tracing._current_trace.set(trace)
    try:
        yield trace
    finally:
        tracing._current_trace.reset(token)


def run_lane(pipeline, lane, question, send):
    trace = StreamTrace(lane, question, send)
    with active(trace):
        try:
            answer = pipeline.invoke({"input": question})["output"]
            stop = "step_limit" if "iteration limit" in answer.lower() else "answered"
            error = None
        except Exception as e:
            answer, stop, error = None, "error", str(e)[:300]
    send({"lane": lane, "type": "done", "answer": answer, "stop": stop, "error": error,
          "seconds": round(trace.events[-1]["t"] if trace.events else 0, 1),
          "cost_usd": round(score_cost(trace.to_dict())["cost_usd"], 4)})


app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check
@app.get("/")
def health_check():
    return JSONResponse(content={
        "message": "Hello from the FastAPI backend!", "default_model": DEFAULT_MODEL,
        "models": [{"id": k, "label": v["label"], "short": v.get("short", v["label"]),
                    "note": v.get("note", ""), "local": v["local"]} for k, v in MODELS.items()]})


@app.get("/schema")
def schema():
    """
    Every table with its columns, and every foreign key (table.column -> table.column).
    """
    return JSONResponse(content={
        "tables": [{"name": t, "columns": cols} for t, cols in sorted(catalog.columns.items())],
        "links": [{"from": t, "column": col, "to": ref, "to_column": ref_col}
                  for t, links in catalog.links.items() for col, ref, ref_col in links]})


@app.get("/examples")
def examples():
    items = {i["id"]: i for suite in ("bim_snowdon", "safety_bim") for i in load_suite(suite)}
    return JSONResponse(content=[{
        "group": group, "question": items[item_id]["question"], "profile": items[item_id]["db_profile"],
        "tables": table_names(items[item_id]["gold_sql"]) if items[item_id].get("gold_sql") else []}
        for group, item_id in EXAMPLES])


def release_after(threads):
    for thread in threads:
        thread.join()
    run_lock.release()


@app.post("/query/stream")
def query_stream(data: dict):
    question = str(data.get("question") or "").strip()
    model = data.get("model") or DEFAULT_MODEL
    if not question:
        raise HTTPException(status_code=400, detail="No question received.")
    if model not in MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'.")
    lanes = ["agent", "baseline"] if data.get("compare") else ["agent"]
    profile = "injected" if data.get("profile") == "injected" else "default"
    print(f"obtaining results: {question} ({model}, {', '.join(lanes)})")

    def events():
        if not run_lock.acquire(blocking=False):
            yield f"data: {json.dumps({'type': 'busy'})}\n\n"
            return
        threads = []
        try:
            built = {lane: pipeline_for(model, lane, profile) for lane in lanes}
            use_model(model)
            inbox = queue.Queue()
            threads = [threading.Thread(target=run_lane, args=(built[lane], lane, question, inbox.put))
                       for lane in lanes]
            for thread in threads:
                thread.start()
            done = 0
            while done < len(lanes):
                event = inbox.get()
                done += event["type"] == "done"
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            # If the browser disconnects, let the running lanes finish before the next question.
            # This can run on a lane's own thread, so the waiting happens on a new one.
            threading.Thread(target=release_after, args=(threads,), daemon=True).start()

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
