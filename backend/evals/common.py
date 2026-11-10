"""
Shared helpers: loading suites, per-profile database engines, running SQL.
"""
import os
import json
import datetime
import decimal
from functools import lru_cache
from sqlalchemy import text

from agents.db_utils import connect_to_db
from evals.profiles import profile_urls, admin_url

EVALS_DIR = os.path.dirname(__file__)
SUITES_DIR = os.path.join(EVALS_DIR, "suites")
RUNS_DIR = os.path.join(EVALS_DIR, "runs")


def load_suite(name: str) -> list:
    """
    Loads suites/<name>.jsonl. Each item gets 'suite' set and defaults for
    optional fields.
    """
    items = []
    with open(os.path.join(SUITES_DIR, f"{name}.jsonl")) as suite_file:
        for line in suite_file:
            if not line.strip():
                continue
            item = json.loads(line)
            item["suite"] = name
            item.setdefault("db_profile", "default")
            item.setdefault("checks", {})
            item.setdefault("tags", [])
            expected = item.get("expected_behavior", "answer")
            item["expected_behavior"] = expected if isinstance(expected, list) else [expected]
            items.append(item)
    return items


@lru_cache(maxsize=None)
def engine_for(profile: str):
    urls = profile_urls()
    if profile not in urls:
        raise KeyError(f"Unknown or unconfigured db_profile '{profile}'. "
                       f"Run `python -m evals.setup_fixtures` first.")
    return connect_to_db(urls[profile])


@lru_cache(maxsize=None)
def admin_engine(database: str = "WideWorldImporters"):
    return connect_to_db(admin_url(database))


def run_sql(engine, sql: str, max_rows: int = 1000):
    """
    Runs a query and returns (columns, rows). Raises on errors.
    """
    with engine.connect() as connection:
        result = connection.execute(text(sql))
        if not result.returns_rows:
            return [], []
        return list(result.keys()), [tuple(row) for row in result.fetchmany(max_rows)]


def normalize_value(value):
    """
    Normalizes a database value for comparison: numbers to rounded floats,
    dates to ISO strings, strings stripped.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, decimal.Decimal)):
        return round(float(value), 4)
    if isinstance(value, datetime.datetime):
        return value.date().isoformat() if value.time() == datetime.time(0) else value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, bytes):
        return "0x" + value.hex().upper()
    return str(value).strip()


def to_jsonable(value):
    value = normalize_value(value)
    return value
