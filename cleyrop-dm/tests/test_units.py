"""Unit tests for parsing, DAG and audits (no Iceberg required)."""

from pathlib import Path

import pyarrow as pa
import pytest

from cleyrop_dm.audits import AuditError, run_audits
from cleyrop_dm.config import ProjectConfig
from cleyrop_dm.dag import Dag
from cleyrop_dm.fingerprint import compute_fingerprints
from cleyrop_dm.model import _extract_table_refs, _split_audits, _split_header, load_models

PROJECT = Path(__file__).parent.parent / "examples" / "retail"


def _project() -> ProjectConfig:
    return ProjectConfig.load(PROJECT)


def test_header_parses_multiline_description_and_audits():
    text = (
        "-- @model: m\n"
        "-- @materialization: incremental\n"
        "-- @description: line one\n"
        "--               line two\n"
        "-- @audits: not_null(a), unique(a)\n"
        "SELECT a FROM src\n"
    )
    header, body = _split_header(text)
    assert header["model"] == "m"
    assert header["description"] == "line one line two"
    assert header["audits"] == "not_null(a), unique(a)"
    assert body.strip() == "SELECT a FROM src"


def test_split_audits_respects_nested_parens():
    assert _split_audits("unique(a, b), not_null(c)") == ["unique(a, b)", "not_null(c)"]


def test_extract_refs_excludes_ctes():
    sql = "WITH t AS (SELECT * FROM raw_orders) SELECT * FROM t JOIN stg_customers USING (id)"
    assert _extract_table_refs(sql) == {"raw_orders", "stg_customers"}


def test_dag_topo_order_and_sources():
    project = _project()
    dag = Dag(load_models(project), project)
    order = dag.topo_order()
    assert order.index("customer_orders") < order.index("customer_features")
    assert dag.upstream("customer_orders") == {"stg_orders", "stg_customers"}


def test_fingerprint_changes_propagate_downstream():
    project = _project()
    models = load_models(project)
    dag = Dag(models, project)
    fps = compute_fingerprints(dag)
    # Mutate an upstream view's body; its descendant fingerprint must change too.
    models["stg_orders"]._sql += "\n-- touched"
    fps2 = compute_fingerprints(dag)
    assert fps2["stg_orders"] != fps["stg_orders"]
    assert fps2["customer_orders"] != fps["customer_orders"]  # descendant dirtied
    assert fps2["stg_customers"] == fps["stg_customers"]      # unrelated unchanged


def test_audits_pass_and_fail():
    t = pa.table({"id": [1, 2, 3], "status": ["a", "a", "b"]})
    run_audits("m", ["not_null(id)", "unique(id)", "accepted_values(status, 'a', 'b')"], t)
    with pytest.raises(AuditError):
        run_audits("m", ["unique(status)"], t)
    with pytest.raises(AuditError):
        run_audits("m", ["expression(id < 3)"], t)
