"""
Validates a suite's gold SQL and writes a review sheet.

    python -m evals.review_suite wwi_dev [safety extraction ...]
    python -m evals.review_suite bim_snowdon --config evals/configs/bim_baseline_qwen7b.yaml

Writes evals/suites/review/<suite>_review.csv with each question, its gold
SQL and the gold result, and flags problems: gold SQL that fails, returns
no rows, or (for TOP 1 questions) has a tie for first place.
"""
import os
import re
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv

from evals.common import SUITES_DIR, load_suite, engine_for, run_sql, normalize_value


def check_top1_tie(engine, sql: str):
    """
    Re-runs a TOP 1 query as TOP 2 WITH TIES-style check: if the second row
    has the same ORDER BY value, the gold answer is ambiguous.
    """
    top = re.search(r"ORDER BY (.+?) DESC\s*$", sql, re.IGNORECASE)
    limit = re.search(r"ORDER BY (.+?) DESC\s+LIMIT 1\s*$", sql, re.IGNORECASE)
    if top and re.search(r"\bTOP 1\b", sql, re.IGNORECASE):  # T-SQL
        order_expr = top.group(1)
        tie_sql = re.sub(r"\bTOP 1\b", "TOP 2", sql, count=1, flags=re.IGNORECASE)
        tie_sql = re.sub(r"SELECT TOP 2 (.+?) FROM", lambda m: f"SELECT TOP 2 {m.group(1)}, {order_expr} AS __order FROM",
                         tie_sql, count=1, flags=re.IGNORECASE | re.DOTALL)
    elif limit:  # SQLite
        order_expr = limit.group(1)
        tie_sql = re.sub(r"LIMIT 1\s*$", "LIMIT 2", sql, flags=re.IGNORECASE)
        tie_sql = re.sub(r"^SELECT (.+?) FROM", lambda m: f"SELECT {m.group(1)}, {order_expr} AS __order FROM",
                         tie_sql, count=1, flags=re.IGNORECASE | re.DOTALL)
    else:
        return None
    _, rows = run_sql(engine, tie_sql)
    if len(rows) == 2 and normalize_value(rows[0][-1]) == normalize_value(rows[1][-1]):
        return f"tie: {rows[0][0]} / {rows[1][0]}"
    return None


def review(suite: str) -> int:
    rows, problems = [], 0
    for item in load_suite(suite):
        gold, flag = "", ""
        if item.get("gold_sql"):
            try:
                engine = engine_for(item["db_profile"])
                columns, result = run_sql(engine, item["gold_sql"])
                gold = "; ".join(", ".join(f"{c}={normalize_value(v)}" for c, v in zip(columns, r))
                                 for r in result[:10])
                if len(result) > 10:
                    gold += f" ... ({len(result)} rows)"
                if not result:
                    flag = "no rows"
                else:
                    flag = check_top1_tie(engine, item["gold_sql"]) or ""
            except Exception as error:
                flag = f"ERROR: {str(error).splitlines()[0][:200]}"
        problems += bool(flag)
        rows.append({"id": item["id"], "category": item.get("category", item.get("difficulty", "")),
                     "question": item["question"], "expected": "|".join(item["expected_behavior"]),
                     "db_profile": item["db_profile"], "checks": item["checks"],
                     "gold_sql": item.get("gold_sql", ""), "gold_result": gold, "flag": flag})
        status = f"  <-- {flag}" if flag else ""
        print(f"{item['id']}: {gold[:90]}{status}")

    out_dir = os.path.join(SUITES_DIR, "review")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{suite}_review.csv")
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\n{suite}: {len(rows)} items, {problems} flagged -> {out_path}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suites", nargs="*", default=["wwi_dev", "safety", "extraction"])
    parser.add_argument("--config", help="run config whose database/profiles to use (e.g. a BIM config)")
    args = parser.parse_args()
    load_dotenv()
    if args.config:
        from evals.run import load_config, apply_config_env
        apply_config_env(load_config(args.config))
    sys.exit(1 if sum(review(suite) for suite in args.suites) else 0)


if __name__ == "__main__":
    main()
