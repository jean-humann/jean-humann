"""Spark Connect engine (distributed).

Spark Connect lets a lightweight client submit work to a remote Spark cluster
over gRPC -- no local JVM, no fat client. This is the production engine for large
Cleyrop datasets; DuckDB is its drop-in local twin.

The transformation contract is identical to :class:`DuckDBEngine`: given the
model SQL and its upstream relations, return an Arrow table. Two execution modes
are supported:

* **Arrow relations** (used by the runner today): upstream Arrow tables are
  turned into temp views and the SQL runs against them. This keeps the engine
  interchangeable with DuckDB.
* **Catalog push-down** (recommended at scale, see :meth:`run_sql_on_catalog`):
  Spark reads the Iceberg tables directly from the shared REST catalog and never
  ships data through the client -- the right choice when tables are large.

This module is written to run against a live Spark Connect server
(``spark.remote`` / ``sc://host:15002``) with Iceberg's Spark runtime on the
cluster. It is not exercised in the local demo because that needs a cluster.
"""

from __future__ import annotations

import pyarrow as pa

from cleyrop_dm.engines.base import Engine


class SparkConnectEngine(Engine):
    name = "spark_connect"

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.remote = self.config.get("remote", "sc://localhost:15002")
        self._spark = None

    @property
    def spark(self):
        if self._spark is None:
            # Imported lazily so the framework works without pyspark installed.
            from pyspark.sql import SparkSession

            builder = SparkSession.builder.remote(self.remote)
            for k, v in self.config.get("conf", {}).items():
                builder = builder.config(k, v)
            self._spark = builder.getOrCreate()
        return self._spark

    def run_sql(self, sql: str, relations: dict[str, pa.Table]) -> pa.Table:
        # Register each upstream Arrow relation as a temp view, then run the SQL.
        for name, table in relations.items():
            self.spark.createDataFrame(table.to_pandas()).createOrReplaceTempView(name)
        return self.spark.sql(sql).toArrow()

    def run_sql_on_catalog(self, sql: str) -> pa.Table:
        """Run SQL that references Iceberg tables by their catalog identifier.

        Nothing is shipped from the client; Spark reads Iceberg directly from the
        shared catalog (``spark_catalog``/REST). Prefer this for large datasets.
        """
        return self.spark.sql(sql).toArrow()

    def close(self) -> None:
        if self._spark is not None:
            self._spark.stop()
