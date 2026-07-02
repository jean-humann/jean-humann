"""Engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pyarrow as pa


class Engine(ABC):
    """Runs SQL over named Arrow relations and returns Arrow.

    The runner materialises each upstream dependency into an Arrow table, hands
    the engine a ``{relation_name: arrow_table}`` map, and asks it to run the
    (already relation-rewritten) SQL. This keeps every engine reading and
    writing the same Iceberg catalog while differing only in *where* the compute
    happens (in-process for DuckDB, on a cluster for Spark Connect).
    """

    name: str

    @abstractmethod
    def run_sql(self, sql: str, relations: dict[str, pa.Table]) -> pa.Table:
        ...

    def close(self) -> None:  # pragma: no cover - optional
        pass
