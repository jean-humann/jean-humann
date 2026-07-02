"""Cleyrop Dataset Management (cleyrop-dm).

A small, opinionated framework for managing Cleyrop datasets -- Apache Iceberg
tables -- with Python and SQL transformations.

It borrows the good ideas from two projects:

* **dbt-core**  -- declarative models, a ref/source DAG, tests, docs and
  materializations.
* **SQLMesh**   -- content fingerprints, change categorisation, and virtual
  data environments with safe blue/green promotion.

...and makes them *native to Iceberg* by using Iceberg branches, tags and
snapshots to implement Write-Audit-Publish (WAP), zero-copy environments and
time travel, instead of re-implementing those semantics in the framework.

Engines are pluggable: DuckDB (embedded), Spark Connect (distributed) and
PyIceberg (metadata + Arrow compute) all read and write the *same* Iceberg
catalog.
"""

from cleyrop_dm.config import Materialization, ModelConfig, ProjectConfig
from cleyrop_dm.model import Model, PythonModel, SqlModel
from cleyrop_dm.dag import Dag

__all__ = [
    "Materialization",
    "ModelConfig",
    "ProjectConfig",
    "Model",
    "SqlModel",
    "PythonModel",
    "Dag",
]

__version__ = "0.1.0"
