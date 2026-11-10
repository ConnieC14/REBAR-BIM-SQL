"""
Compares two scored runs question by question.

    python -m evals.compare evals/runs/<A> evals/runs/<B>

Writes compare_<A>_vs_<B>.md into run B's folder: metric deltas, the
questions B fixed or broke, McNemar's exact test on pass/fail and a paired
bootstrap interval for cost and latency.
"""
import os
import sys
import json
import random
from math import comb
import pandas as pd


def per_item(run_dir: str) -> pd.DataFrame:
    """
    One row per question: pass if the majority of its repeats passed.
    """
    results = pd.read_csv(os.path.join(run_dir, "results.csv"))
    return results.groupby(["suite", "id"]).agg(
        passed=("passed", lambda s: int(s.mean() >= 0.5)),
        cost_usd=("cost_usd", "mean"),
        latency_s=("latency_s", "mean"),
        steps=("steps", "mean")).reset_index()


def mcnemar_exact(b_only: int, a_only: int) -> float:
    """
    Two-sided exact McNemar p-value from the discordant pair counts.
    """
    n = b_only + a_only
    if n == 0:
        return 1.0
    k = min(b_only, a_only)
    p = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def bootstrap_diff(a: pd.Series, b: pd.Series, iterations: int = 2000, seed: int = 0):
    """
    95% interval for mean(b - a) over paired questions.
    """
    diffs = (b - a).dropna().tolist()
    if not diffs:
        return None, None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(iterations))
    return means[int(0.025 * iterations)], means[int(0.975 * iterations)]


def compare(run_a: str, run_b: str) -> str:
    name_a, name_b = os.path.basename(run_a.rstrip("/")), os.path.basename(run_b.rstrip("/"))
    a, b = per_item(run_a), per_item(run_b)
    merged = a.merge(b, on=["suite", "id"], suffixes=("_a", "_b"))
    lines = [f"# {name_b} vs {name_a}", "", f"{len(merged)} questions in both runs.", ""]

    with open(os.path.join(run_a, "summary.json")) as f_a, open(os.path.join(run_b, "summary.json")) as f_b:
        summary_a, summary_b = json.load(f_a), json.load(f_b)

    for suite, frame in merged.groupby("suite"):
        fixed = frame[(frame.passed_a == 0) & (frame.passed_b == 1)]
        broken = frame[(frame.passed_a == 1) & (frame.passed_b == 0)]
        p_value = mcnemar_exact(len(fixed), len(broken))
        lines += [f"## {suite}", "",
                  "| Metric | A | B | Δ |", "|---|---|---|---|",
                  f"| pass rate | {frame.passed_a.mean():.0%} | {frame.passed_b.mean():.0%} | "
                  f"{frame.passed_b.mean() - frame.passed_a.mean():+.0%} |"]
        metrics_a = summary_a["suites"].get(suite, {}).get("metrics", {})
        metrics_b = summary_b["suites"].get(suite, {}).get("metrics", {})
        for metric in metrics_b:
            mean_a, mean_b = metrics_a.get(metric, {}).get("mean"), metrics_b[metric].get("mean")
            if mean_a is not None and mean_b is not None:
                lines.append(f"| {metric} | {mean_a:.0%} | {mean_b:.0%} | {mean_b - mean_a:+.0%} |")
        for metric in ("cost_usd", "latency_s", "steps"):
            low, high = bootstrap_diff(frame[f"{metric}_a"], frame[f"{metric}_b"])
            interval = f" (95% CI {low:+.4g} to {high:+.4g})" if low is not None else ""
            lines.append(f"| {metric} (mean) | {frame[f'{metric}_a'].mean():.4g} | "
                         f"{frame[f'{metric}_b'].mean():.4g} | "
                         f"{frame[f'{metric}_b'].mean() - frame[f'{metric}_a'].mean():+.4g}{interval} |")
        lines += ["", f"Fixed by B: {len(fixed)}, broken by B: {len(broken)}, "
                      f"McNemar exact p = {p_value:.3f}", ""]
        if len(fixed):
            lines.append("- Fixed: " + ", ".join(f"`{i}`" for i in fixed.id))
        if len(broken):
            lines.append("- Broken: " + ", ".join(f"`{i}`" for i in broken.id))
        lines.append("")

    report = "\n".join(lines)
    out_path = os.path.join(run_b, f"compare_{name_a}_vs_{name_b}.md")
    with open(out_path, "w") as out_file:
        out_file.write(report)
    print(report)
    print(f"Wrote {out_path}")
    return out_path


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    compare(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
