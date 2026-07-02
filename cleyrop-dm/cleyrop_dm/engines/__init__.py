"""Pluggable execution engines.

Every engine reads and writes the *same* Iceberg catalog. The framework only
needs an engine to do one thing: run a SQL statement against a set of named
Arrow relations and return the result as an Arrow table. Materialisation into
Iceberg is handled centrally by :mod:`cleyrop_dm.catalog`, so adding an engine
is cheap.
"""

from cleyrop_dm.engines.base import Engine
from cleyrop_dm.engines.duckdb_engine import DuckDBEngine


def get_engine(name: str, config: dict) -> Engine:
    if name == "duckdb":
        return DuckDBEngine(config)
    if name == "spark_connect":
        from cleyrop_dm.engines.spark_connect_engine import SparkConnectEngine

        return SparkConnectEngine(config)
    raise ValueError(f"Unknown engine: {name!r}")


__all__ = ["Engine", "DuckDBEngine", "get_engine"]
