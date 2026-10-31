"""Read-only DuckDB access and file locations.

Each request opens its own short-lived read-only connection: cheap in DuckDB, and it never holds a
lock while dbt or ml.score are not running. (DuckDB still refuses a writer while a reader is open,
so stop the API before `make dbt` / `make score`.)
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import duckdb

ROOT = Path(__file__).resolve().parent.parent


def warehouse_path() -> Path:
    return Path(os.getenv("WAREHOUSE_PATH", ROOT / "data" / "warehouse.duckdb"))


def metrics_path() -> Path:
    return Path(os.getenv("METRICS_PATH", ROOT / "ml" / "models" / "metrics.json"))


def brief_cache_path() -> Path:
    return Path(os.getenv("BRIEF_CACHE_PATH", ROOT / "data" / "app.sqlite"))


@contextmanager
def connect() -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect(str(warehouse_path()), read_only=True)
    try:
        yield con
    finally:
        con.close()


def fetch_all(sql: str, params: list | None = None) -> list[dict[str, Any]]:
    with connect() as con:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_one(sql: str, params: list | None = None) -> dict[str, Any] | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
