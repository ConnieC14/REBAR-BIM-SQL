"""
Database profiles: which database (and login) a question runs against.

    default              DB_URL (set from the run config's `database`, or .env)

SQL Server (WideWorldImporters) adds:
    restricted_far_west  agent_far_west, Far West Sales territory only (row-level security tests)
    injected             agent_reader on WideWorldImporters_Safety (planted prompt injections)

Any database adds the profiles in the config's `profiles` mapping
(passed as EXTRA_DB_PROFILES), e.g. a second BIM model.
"""
import os
import json
from sqlalchemy.engine import make_url

MAIN_DB = "WideWorldImporters"
SAFETY_DB = "WideWorldImporters_Safety"
RESTRICTED_ENV = "DB_URL_RESTRICTED_FAR_WEST"


def _render(url) -> str:
    return url.render_as_string(hide_password=False)


def sqlite_url(path: str) -> str:
    """
    Read-only SQLite URL for a database file (relative paths are resolved
    from the backend/ directory).
    """
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    absolute = path if os.path.isabs(path) else os.path.join(backend_dir, path)
    if not os.path.exists(absolute):
        raise FileNotFoundError(f"SQLite database not found: {absolute}")
    return f"sqlite:///file:{absolute}?mode=ro&uri=true"


def profile_urls() -> dict:
    default = make_url(os.environ["DB_URL"])
    urls = {"default": _render(default)}
    if default.drivername.startswith("mssql"):
        urls["injected"] = _render(default.set(database=SAFETY_DB))
        if os.getenv(RESTRICTED_ENV):
            urls["restricted_far_west"] = os.environ[RESTRICTED_ENV]
    for name, path in json.loads(os.getenv("EXTRA_DB_PROFILES", "{}")).items():
        urls[name] = sqlite_url(path) if path.endswith(".db") else path
    return urls


def admin_url(database=MAIN_DB) -> str:
    """
    sa login, used only by the harness itself (fixtures and looking up
    sensitive values to detect leaks), never by the agent.
    """
    default = make_url(os.environ["DB_URL"])
    return _render(default.set(username="sa", password=os.environ["MSSQL_SA_PASSWORD"],
                               database=database))
