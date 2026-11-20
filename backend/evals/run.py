"""
Runs a pipeline config over the question suites and scores it.
    python -m evals.run --config evals/configs/baseline_qwen7b.yaml [--limit 3] [--ids ...]
"""
import os
import sys
import json
import argparse
import datetime
import traceback
import importlib.metadata
import yaml
from dotenv import load_dotenv

from evals.common import RUNS_DIR, load_suite
from utils.tracing import start_trace

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
PACKAGES = ["anthropic", "langchain", "langchain-openai", "chromadb", "SQLAlchemy",
            "pymssql", "sentence-transformers"]


def load_config(path: str) -> dict:
    with open(path) as config_file:
        config = yaml.safe_load(config_file)
    config.setdefault("pipeline", "baseline")
    config.setdefault("retrieval", "baseline")
    config.setdefault("repeats", 1)
    config.setdefault("suites", ["wwi_dev", "safety", "extraction"])
    config.setdefault("budget_usd", 5.0)
    config.setdefault("judge", None)
    config.setdefault("limits", {})
    config.setdefault("safety", False)
    for variant in ("refine", "fewshot", "notes", "tool_calling"):   # agents/variants.py
        config.setdefault(variant, False)
    return config


def apply_config_env(config: dict):
    """
    The pipeline reads its settings from environment variables, so a config
    is applied by setting them before the pipeline modules are imported.
    """
    llm = config.get("llm", {})
    settings = {
        "LLM_PROVIDER": llm.get("provider"),
        "LLM_MODEL": llm.get("model"),
        "LLM_EFFORT": llm.get("effort"),
        "LLM_BASE_URL": llm.get("base_url"),
        "EMBEDDING_PROVIDER": config.get("embeddings", "local"),
        "METADATA_SOURCE": config.get("metadata_source", "db"),
        "RETRIEVAL": config["retrieval"],
        "MAX_STEPS": config["limits"].get("max_steps", 6),
        "SQL_TIMEOUT_S": config["limits"].get("sql_timeout_s", 30),
        "SQL_MAX_ROWS": config["limits"].get("max_rows", 200),
        "AGENT_VERBOSE": "0",
        # +safety (true): read-only guard and prompt rules; +guard ("guard"): guard only
        "SAFETY": "guard" if config["safety"] == "guard" else "1" if config["safety"] else "0",
        # +refine, +fewshot, +notes, +tools (agents/variants.py)
        "REFINE": "1" if config["refine"] else "0",
        "FEWSHOT": "1" if config["fewshot"] else "0",
        "NOTES": "1" if config["notes"] else "0",
        "TOOL_CALLING": "1" if config["tool_calling"] else "0",
        # Each database keeps its own vector store (collections are not rebuilt if they exist)
        "CHROMA_DB_PATH": config.get("chroma_path"),
    }
    if config.get("database"):
        from evals.profiles import sqlite_url
        database = config["database"]
        settings["DB_URL"] = sqlite_url(database) if database.endswith(".db") else database
    if config.get("profiles"):
        settings["EXTRA_DB_PROFILES"] = json.dumps(config["profiles"])
    for key, value in settings.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)


def build_pipeline_for(config: dict):
    """
    Pipeline variants. Add new ones here (e.g. "self_correct") as they are built.
    """
    from agents.agents_pipeline import build_pipeline
    variants = {"baseline": build_pipeline}
    if config["pipeline"] not in variants:
        raise ValueError(f"Unknown pipeline '{config['pipeline']}'. Known: {list(variants)}")
    return variants[config["pipeline"]]


def package_versions() -> dict:
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def select_items(config: dict, args) -> list:
    items = []
    for suite in args.suites or config["suites"]:
        suite_items = load_suite(suite)
        if args.ids:
            suite_items = [item for item in suite_items if item["id"] in args.ids]
        if args.limit:
            suite_items = suite_items[:args.limit]
        items += suite_items
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--limit", type=int, help="first N items of each suite")
    parser.add_argument("--ids", nargs="+", help="only these item ids")
    parser.add_argument("--suites", nargs="+", help="override the config's suites")
    parser.add_argument("--repeats", type=int, help="override the config's repeats")
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    config = load_config(args.config)
    if args.repeats:
        config["repeats"] = args.repeats
    if config["judge"]:
        sys.exit("The LLM judge is not implemented yet; set `judge: null` in the config.")
    apply_config_env(config)

    # Pipeline modules read the environment at import time, so import after apply_config_env
    from scripts.chromadb_table_column_descriptions import ChromaDBManager
    from vector_db_agent_pipeline import populate_metadata
    from evals.common import engine_for
    from evals.scorers import score_cost, schema_elements, SQLGLOT_DIALECTS
    from evals.report import build_outputs
    from agents.retrieval import set_oracle_tables

    items = select_items(config, args)
    plan = [(item, repeat) for item in items for repeat in range(config["repeats"])]

    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = os.path.join(RUNS_DIR, f"{stamp}_{config['name']}")
    os.makedirs(run_dir)
    meta = {"started": stamp, "args": vars(args), "packages": package_versions(),
            "planned_runs": len(plan)}
    with open(os.path.join(run_dir, "config.yaml"), "w") as config_file:
        yaml.safe_dump({**config, "_meta": meta}, config_file, sort_keys=False)
    with open(os.path.join(run_dir, "items.jsonl"), "w") as items_file:
        for item in items:
            items_file.write(json.dumps(item) + "\n")

    print(f"Run {run_dir}\n{len(items)} items x {config['repeats']} repeats = {len(plan)} runs, "
          f"budget ${config['budget_usd']:.2f}")

    manager = ChromaDBManager()
    populate_metadata(manager, engine_for("default"), "./data")
    build_pipeline = build_pipeline_for(config)
    pipelines = {}

    total_cost, completed, budget_stopped = 0.0, 0, False
    traces_path = os.path.join(run_dir, "traces.jsonl")
    for index, (item, repeat) in enumerate(plan, start=1):
        if total_cost >= config["budget_usd"]:
            budget_stopped = True
            print(f"Budget of ${config['budget_usd']:.2f} reached; stopping after {completed} runs.")
            break

        profile = item["db_profile"]
        if profile not in pipelines:
            pipelines[profile] = build_pipeline(manager, engine_for(profile))
        if config["retrieval"] == "oracle":
            # Only the gold query's table names reach retrieval, never the query itself
            dialect = SQLGLOT_DIALECTS.get(engine_for(profile).dialect.name, "tsql")
            set_oracle_tables(schema_elements(item["gold_sql"], dialect)[0] or []
                              if item.get("gold_sql") else [])

        with start_trace(item["id"], item["question"]) as trace:
            try:
                output = pipelines[profile].invoke({"input": item["question"]})["output"]
                trace.final_answer = output
                trace.stop_reason = "step_limit" if "iteration limit" in output.lower() else "answered"
            except Exception as error:
                trace.stop_reason = "error"
                trace.error = "".join(traceback.format_exception_only(type(error), error)).strip()[:2000]

        record = {**trace.to_dict(), "suite": item["suite"], "repeat": repeat, "db_profile": profile}
        with open(traces_path, "a") as traces_file:
            traces_file.write(json.dumps(record, default=str) + "\n")

        cost = score_cost(record)["cost_usd"]
        total_cost += cost
        completed += 1
        projected = total_cost / completed * len(plan)
        print(f"[{index}/{len(plan)}] {item['id']} r{repeat} {trace.stop_reason:<10} "
              f"{trace.latency_s:6.1f}s ${cost:.4f}  (total ${total_cost:.4f}, projected ${projected:.2f})")
        if completed == 5 and projected > config["budget_usd"]:
            print(f"WARNING: projected cost ${projected:.2f} exceeds the budget; "
                  f"the run will stop early at ${config['budget_usd']:.2f}.")

    meta.update({"completed_runs": completed, "budget_stopped": budget_stopped,
                 "total_cost_usd": round(total_cost, 4),
                 "finished": datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")})
    with open(os.path.join(run_dir, "config.yaml"), "w") as config_file:
        yaml.safe_dump({**config, "_meta": meta}, config_file, sort_keys=False)

    build_outputs(run_dir)
    print(f"\nDone: {run_dir}")


if __name__ == "__main__":
    main()
