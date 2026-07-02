"""Embedded DuckDB engine.

DuckDB runs the transformation in-process. Upstream Iceberg data is handed to it
as Arrow tables (zero-copy), registered as views, and the model SQL runs against
them. Ideal for local development, CI, and small/medium datasets -- the same SQL
runs unchanged on Spark Connect at scale.
"""

from __future__ import annotations

import duckdb
import pyarrow as pa

from cleyrop_dm.engines.base import Engine


class DuckDBEngine(Engine):
    name = "duckdb"

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._con = duckdb.connect(self.config.get("database", ":memory:"))

    def run_sql(self, sql: str, relations: dict[str, pa.Table]) -> pa.Table:
        con = self._con.cursor()  # isolated so registrations don't leak
        try:
            for name, table in relations.items():
                con.register(name, table)
            return con.execute(sql).to_arrow_table()
        finally:
            con.close()

    def close(self) -> None:
        self._con.close()
