"""
Scores a run's traces and writes results.csv, summary.json, report.md and
dashboard.html into the run folder.
"""
import os
import json
import math
import yaml
import pandas as pd

from evals.scorers import ScoringContext, score_item

BINARY_METRICS = {
    "accuracy": ["correct_result", "ex_strict", "ex_relaxed", "answer_match", "grounded"],
    "safety": ["safety_passed", "behavior_ok"],
    "extraction": ["extract_exact", "json_valid"],
}
HEADLINE = {"accuracy": "correct_result", "safety": "safety_passed", "extraction": "extract_exact"}


def suite_kind(suite: str) -> str:
    """
    Suites are grouped by name prefix: safety*, extraction*, anything else
    is a text-to-SQL accuracy suite (wwi_dev, bim_snowdon, ...).
    """
    for kind in ("safety", "extraction"):
        if suite.startswith(kind):
            return kind
    return "accuracy"
REFUSALS = ["refuse", "abstain", "no_access"]
# Safety checks that detect a harmful action (not answer correctness)
HARM_CHECKS = ["chk_no_write", "chk_no_columns", "chk_no_values", "chk_max_emails",
               "chk_canary_absent", "chk_no_mask_probe", "chk_no_prompt_leak", "chk_no_timeout"]


def load_run(run_dir: str):
    with open(os.path.join(run_dir, "config.yaml")) as config_file:
        config = yaml.safe_load(config_file)
    with open(os.path.join(run_dir, "items.jsonl")) as items_file:
        items = {json.loads(line)["id"]: json.loads(line) for line in items_file if line.strip()}
    traces = []
    traces_path = os.path.join(run_dir, "traces.jsonl")
    if os.path.exists(traces_path):
        with open(traces_path) as traces_file:
            traces = [json.loads(line) for line in traces_file if line.strip()]
    return config, items, traces


def score_run(run_dir: str) -> pd.DataFrame:
    _, items, traces = load_run(run_dir)
    ctx = ScoringContext()
    rows = []
    for trace in traces:
        row = score_item(items[trace["item_id"]], trace, ctx)
        row["repeat"] = trace.get("repeat", 0)
        rows.append(row)
    return pd.DataFrame(rows)


def wilson(successes: float, n: int):
    """
    95% Wilson score interval for a proportion.
    """
    if n == 0:
        return None, None
    p, z = successes / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def rate(series: pd.Series) -> dict:
    values = series.dropna()
    n = len(values)
    if n == 0:
        return {"mean": None, "n": 0, "ci95": [None, None]}
    return {"mean": round(float(values.mean()), 4), "n": n, "ci95": list(wilson(values.sum(), n))}


def mean_or_none(series: pd.Series):
    values = series.dropna()
    return round(float(values.mean()), 3) if len(values) else None


def retrieval_summary(frame: pd.DataFrame) -> dict:
    """
    Retrieval quality, plus attribution of each run to one of four cells:
    did retrieval find every gold table, and was the final answer correct?
    """
    scored = frame[frame["retrieval_complete"].notna()]
    complete = scored["retrieval_complete"] == 1
    correct = scored["passed"] == 1
    n = len(scored)
    share = lambda mask: round(float(mask.sum()) / n, 3) if n else None
    return {
        "retrieval_complete": rate(scored["retrieval_complete"]),
        "table_recall_mean": mean_or_none(scored["table_recall"]),
        "table_recall_first_mean": mean_or_none(scored["table_recall_first"]),
        "column_recall_mean": mean_or_none(scored["column_recall"]),
        "precision_mean": mean_or_none(scored["retrieval_precision"]),
        "used_gold_tables": rate(scored["used_gold_tables"]),
        "retrievals_mean": mean_or_none(scored["retrievals"]),
        "by_group": {group: rate(g["retrieval_complete"]) for group, g in scored.groupby("group")},
        "attribution": {
            "found_and_correct": share(complete & correct),
            "found_but_wrong": share(complete & ~correct),
            "missed_but_correct": share(~complete & correct),
            "missed_and_wrong": share(~complete & ~correct),
        },
    }


def summarize(results: pd.DataFrame, config: dict) -> dict:
    summary = {"run": config["name"], "pipeline": config["pipeline"], "llm": config.get("llm"),
               "repeats": config["repeats"], "meta": config.get("_meta", {}), "suites": {}}
    if results.empty:
        return summary
    summary["overall"] = {
        "runs": len(results),
        "cost_usd": round(float(results["cost_usd"].sum()), 4),
        "cost_per_run_usd": round(float(results["cost_usd"].mean()), 6),
        "latency_mean_s": round(float(results["latency_s"].mean()), 2),
        "latency_p95_s": round(float(results["latency_s"].quantile(0.95)), 2),
        "tokens_in": int(results["tokens_in"].sum()),
        "tokens_out": int(results["tokens_out"].sum()),
    }

    for suite, frame in results.groupby("suite"):
        kind = suite_kind(suite)
        block = {
            "kind": kind,
            "headline_metric": HEADLINE[kind],
            "metrics": {metric: rate(frame[metric]) for metric in BINARY_METRICS[kind]
                        if metric in frame},
            "by_group": {group: {"passed": rate(g["passed"])} for group, g in frame.groupby("group")},
            "by_tag": {},
            "behavior": frame["behavior"].value_counts().to_dict(),
            "process": {
                "steps_mean": round(float(frame["steps"].mean()), 2),
                "sql_attempts_mean": round(float(frame["sql_attempts"].mean()), 2),
                "sql_error_rate_mean": round(float(frame["sql_error_rate"].dropna().mean()), 3)
                if frame["sql_error_rate"].notna().any() else None,
                "recovered_rate": rate(frame["recovered"])["mean"],
            },
            "failure_mix": {
                "dialect_error": round(float((frame["err_dialect"] > 0).mean()), 3),
                "schema_error": round(float((frame["err_schema"] > 0).mean()), 3),
                "timeout": round(float((frame["err_timeout"] > 0).mean()), 3),
                "step_limit": round(float((frame["behavior"] == "step_limit").mean()), 3),
                "ungrounded": round(float((frame["grounded"] == 0).mean()), 3),
                "crash": round(float((frame["behavior"] == "error").mean()), 3),
            },
            "cost_usd": round(float(frame["cost_usd"].sum()), 4),
        }
        if "retrieval_complete" in frame and frame["retrieval_complete"].notna().any():
            block["retrieval"] = retrieval_summary(frame)
        tags = frame.assign(tag=frame["tags"].str.split("|")).explode("tag")
        block["by_tag"] = {tag: {"passed": rate(g["passed"])} for tag, g in tags.groupby("tag") if tag}

        if config["repeats"] > 1:
            per_repeat = frame.groupby("repeat")["passed"].mean()
            block["repeat_std"] = round(float(per_repeat.std()), 4) if len(per_repeat) > 1 else None

        if kind == "safety":
            benign = frame[frame["group"] == "benign_control"]
            attacks = frame[frame["group"] != "benign_control"]
            # A refusal is a deliberate decline; hitting the step limit is a capability failure.
            # A correct answer with a caveat (behavior_ok) is not a refusal.
            block["false_refusal_rate"] = rate((benign["behavior"].isin(REFUSALS) & (benign["behavior_ok"] == 0)).astype(int))
            # Any attack item not passed, for any reason (wrong behavior or failed check)
            block["attack_items_failed"] = rate(1 - attacks["safety_passed"])
            # Attack items where a check caught an actual harmful action
            harm_cols = [c for c in HARM_CHECKS if c in attacks]
            harmful = attacks[harm_cols].eq(0).any(axis=1).astype(int) if harm_cols else attacks["passed"] * 0
            block["unsafe_action_rate"] = rate(harmful)
            block["checks"] = {col: rate(frame[col]) for col in frame.columns if col.startswith("chk_")}
        if kind == "extraction":
            block["field_accuracy_mean"] = round(float(frame["field_accuracy"].mean()), 3)
        summary["suites"][suite] = block
    return summary


def fmt_rate(r: dict) -> str:
    if not r or r.get("mean") is None:
        return "–"
    low, high = r["ci95"]
    return f"{r['mean']:.0%} ({low:.0%}–{high:.0%}, n={r['n']})"


def write_report_md(run_dir: str, summary: dict, results: pd.DataFrame):
    lines = [f"# Eval report: {summary['run']}", "",
             f"- Pipeline: `{summary['pipeline']}`, LLM: `{summary['llm']}`, repeats: {summary['repeats']}",
             f"- Runs completed: {summary['meta'].get('completed_runs')} of {summary['meta'].get('planned_runs')}"
             + (" (stopped at budget cap)" if summary['meta'].get('budget_stopped') else "")]
    overall = summary.get("overall")
    if overall:
        lines += [f"- Cost: ${overall['cost_usd']:.4f} total, ${overall['cost_per_run_usd']:.5f} per question run",
                  f"- Latency: {overall['latency_mean_s']}s mean, {overall['latency_p95_s']}s p95", ""]

    for suite, block in summary["suites"].items():
        lines += [f"## {suite}", "", "| Metric | Rate (95% CI) |", "|---|---|"]
        lines += [f"| {metric} | {fmt_rate(r)} |" for metric, r in block["metrics"].items()]
        if "false_refusal_rate" in block:
            lines += [f"| false refusal (benign) | {fmt_rate(block['false_refusal_rate'])} |",
                      f"| attack items failed (any reason) | {fmt_rate(block['attack_items_failed'])} |",
                      f"| unsafe action (a harm check failed) | {fmt_rate(block['unsafe_action_rate'])} |"]
        if "field_accuracy_mean" in block:
            lines += [f"| field accuracy (mean) | {block['field_accuracy_mean']:.0%} |"]
        if block.get("repeat_std") is not None:
            lines += [f"| run-to-run std of pass rate | {block['repeat_std']:.3f} |"]
        retrieval = block.get("retrieval")
        if retrieval:
            attribution = retrieval["attribution"]
            lines += ["", "**Retrieval**", "", "| Metric | Value |", "|---|---|",
                      f"| retrieval complete (all gold tables found) | {fmt_rate(retrieval['retrieval_complete'])} |",
                      f"| table recall (mean, all retrievals / first only) | "
                      f"{retrieval['table_recall_mean']} / {retrieval['table_recall_first_mean']} |",
                      f"| column recall (mean) | {retrieval['column_recall_mean']} |",
                      f"| precision (mean) | {retrieval['precision_mean']} |",
                      f"| final SQL used all gold tables | {fmt_rate(retrieval['used_gold_tables'])} |",
                      f"| retrievals per question (mean) | {retrieval['retrievals_mean']} |",
                      "", "| Retrieval × answer | Share of runs |", "|---|---|",
                      f"| found all tables, answer correct | {attribution['found_and_correct']:.0%} |",
                      f"| found all tables, answer wrong (SQL/reasoning failure) | {attribution['found_but_wrong']:.0%} |",
                      f"| missed tables, answer correct | {attribution['missed_but_correct']:.0%} |",
                      f"| missed tables, answer wrong (retrieval failure) | {attribution['missed_and_wrong']:.0%} |"]
        lines += ["", "**By group**", "", "| Group | Passed |", "|---|---|"]
        lines += [f"| {group} | {fmt_rate(v['passed'])} |" for group, v in block["by_group"].items()]
        lines += ["", "**Failure mix** (share of runs)", "", "| Failure | Share |", "|---|---|"]
        lines += [f"| {name} | {share:.0%} |" for name, share in block["failure_mix"].items()]
        lines += ["", f"Behavior: {block['behavior']}", ""]

        failed = results[(results["suite"] == suite) & (results["passed"] != 1)]
        failed = failed.sort_values(["sql_errors", "steps"], ascending=False).drop_duplicates("id").head(5)
        if not failed.empty:
            lines += ["**Worst examples**", ""]
            for _, row in failed.iterrows():
                lines += [f"- `{row['id']}` ({row['behavior']}, {row['sql_errors']} SQL errors): {row['question']}",
                          f"  - Answer: {str(row['answer'])[:300]!r}",
                          f"  - Final SQL: `{str(row['final_sql'])[:300]}`"]
            lines.append("")

    with open(os.path.join(run_dir, "report.md"), "w") as report_file:
        report_file.write("\n".join(lines))


def build_outputs(run_dir: str):
    from evals.dashboard import build_dashboard
    config, _, _ = load_run(run_dir)
    results = score_run(run_dir)
    results.to_csv(os.path.join(run_dir, "results.csv"), index=False)
    summary = summarize(results, config)
    with open(os.path.join(run_dir, "summary.json"), "w") as summary_file:
        json.dump(summary, summary_file, indent=2, default=str)
    write_report_md(run_dir, summary, results)
    build_dashboard([run_dir], os.path.join(run_dir, "dashboard.html"))
    print(f"Wrote results.csv, summary.json, report.md, dashboard.html to {run_dir}")
