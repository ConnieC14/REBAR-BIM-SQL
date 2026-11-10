"""
One row per question showing how it did in each run of a suite.

    python -m evals.question_results bim_snowdon                 # latest full run of each config
    python -m evals.question_results bim_snowdon evals/runs/<A> evals/runs/<B>

Writes evals/suites/review/<suite>_results.csv. For each run, "<run> pass" is
the number of repeats that passed (e.g. 2/3) and "<run> tables" the number
whose retrieval found every gold table. "passed in" lists the runs where the
question passed by majority.
"""
import os
import sys
import glob
import argparse
import yaml
import pandas as pd

from evals.common import RUNS_DIR, SUITES_DIR, load_suite

# Column order for the retrieval variants, weakest to strongest
RETRIEVAL_ORDER = ["baseline", "static_search", "agentic_search", "agentic_values", "oracle"]


def run_label(run_dir: str) -> str:
    with open(os.path.join(run_dir, "config.yaml")) as config_file:
        name = yaml.safe_load(config_file)["name"]
    return name.removeprefix("bim_")


def latest_full_runs(suite: str) -> list:
    """
    The most recent run of each config that scored every question of the suite.
    """
    suite_size = len(load_suite(suite))
    latest = {}
    for run_dir in sorted(glob.glob(os.path.join(RUNS_DIR, "*"))):
        results_path = os.path.join(run_dir, "results.csv")
        if not os.path.exists(results_path):
            continue
        results = pd.read_csv(results_path)
        if results[results.suite == suite]["id"].nunique() == suite_size:
            with open(os.path.join(run_dir, "config.yaml")) as config_file:
                config = yaml.safe_load(config_file)
            latest[config["name"]] = (config.get("retrieval", "baseline"), run_dir)
    ordered = sorted(latest.values(), key=lambda r: (RETRIEVAL_ORDER.index(r[0])
                                                     if r[0] in RETRIEVAL_ORDER else len(RETRIEVAL_ORDER), r[1]))
    return [run_dir for _, run_dir in ordered]


def question_results(suite: str, run_dirs: list) -> pd.DataFrame:
    table = pd.DataFrame([{"id": item["id"], "difficulty": item.get("difficulty", ""),
                           "question": item["question"]} for item in load_suite(suite)])
    passed_in = {question_id: [] for question_id in table["id"]}
    for run_dir in run_dirs:
        label = run_label(run_dir)
        results = pd.read_csv(os.path.join(run_dir, "results.csv"))
        per_question = results[results.suite == suite].groupby("id").agg(
            passes=("passed", "sum"), tables=("retrieval_complete", "sum"), repeats=("passed", "size"))
        table[f"{label} pass"] = table["id"].map(
            lambda q: f"{int(per_question.passes[q])}/{per_question.repeats[q]}" if q in per_question.index else "")
        table[f"{label} tables"] = table["id"].map(
            lambda q: f"{int(per_question.tables[q])}/{per_question.repeats[q]}" if q in per_question.index else "")
        for question_id, row in per_question.iterrows():
            if row.passes / row.repeats >= 0.5:
                passed_in[question_id].append(label)
    table["passed in"] = table["id"].map(lambda q: ", ".join(passed_in[q]) or "none")
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite")
    parser.add_argument("runs", nargs="*", help="run folders (default: latest full run of each config)")
    args = parser.parse_args()

    run_dirs = args.runs or latest_full_runs(args.suite)
    if not run_dirs:
        sys.exit(f"No run has scored every question of {args.suite}.")
    table = question_results(args.suite, run_dirs)
    out_path = os.path.join(SUITES_DIR, "review", f"{args.suite}_results.csv")
    table.to_csv(out_path, index=False)
    print("Runs:\n" + "\n".join(f"  {run_label(r)}: {r}" for r in run_dirs))
    print(f"{len(table)} questions -> {out_path}")
    print(table["passed in"].value_counts().to_string())


if __name__ == "__main__":
    main()
