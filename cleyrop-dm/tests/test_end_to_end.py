"""End-to-end tests against a real (local) Iceberg warehouse."""

import tempfile
from pathlib import Path

import pyarrow as pa
import pytest
from pyiceberg.catalog.sql import SqlCatalog

from cleyrop_dm.audits import AuditError
from cleyrop_dm.config import ProjectConfig
from cleyrop_dm.runner import Runner

PROJECT = Path(__file__).parent.parent / "examples" / "retail"


def _orders(rows):
    c = list(zip(*rows))
    return pa.table({
        "order_id": pa.array(c[0], pa.int64()),
        "customer_id": pa.array(c[1], pa.int64()),
        "order_ts": pa.array(c[2], pa.string()),
        "status": pa.array(c[3], pa.string()),
        "amount": pa.array(c[4], pa.float64()),
    })


@pytest.fixture()
def runner():
    wh = tempfile.mkdtemp(prefix="cleyrop_test_")
    props = {"type": "sql", "uri": f"sqlite:///{wh}/c.db", "warehouse": f"file://{wh}"}
    # Catalog name must match the project name -- SqlCatalog keys rows by it.
    cat = SqlCatalog("retail", **props)
    cat.create_namespace("raw")
    cat.create_table("raw.customers", schema=pa.table({
        "customer_id": pa.array([1, 2, 3], pa.int64()),
        "name": ["A", "B", "C"], "country": ["FR", "DE", "FR"]}).schema
    ).append(pa.table({"customer_id": pa.array([1, 2, 3], pa.int64()),
                       "name": ["A", "B", "C"], "country": ["FR", "DE", "FR"]}))
    cat.create_table("raw.orders", schema=_orders([(1, 1, "2026-06-01", "paid", 10.0)]).schema
    ).append(_orders([
        (1, 1, "2026-06-01", "paid", 10.0),
        (2, 2, "2026-06-01", "paid", 20.0),
        (3, 3, "2026-06-02", "new", 5.0),
    ]))
    project = ProjectConfig.load(PROJECT)
    project.catalog = dict(props)
    r = Runner(project, state_path=Path(wh) / "state.db")
    yield r
    r.close()


def _rev(runner, env):
    t = runner.catalog.scan_env(runner.catalog.identifier("daily_revenue"), env)
    return dict(zip([str(d) for d in t.to_pydict()["order_date"]], t.to_pydict()["revenue"]))


def test_first_apply_is_idempotent(runner):
    plan = runner.plan("prod")
    assert plan.has_changes
    runner.apply(plan)
    # Second plan sees no changes -- fingerprints match applied state.
    assert not runner.plan("prod").has_changes


def test_dev_branch_isolated_then_promote(runner):
    runner.run("prod")
    assert _rev(runner, "prod") == {"2026-06-01": 30.0}
    # New data + incremental run in dev only.
    runner.catalog.catalog.load_table("raw.orders").append(
        _orders([(4, 1, "2026-06-03", "paid", 100.0)]))
    runner.run("dev", select={"daily_revenue"}, force=True)
    assert "2026-06-03" in _rev(runner, "dev")
    assert "2026-06-03" not in _rev(runner, "prod")  # prod untouched (WAP)
    # Promote dev -> prod.
    runner.promote("dev", "prod", select={"daily_revenue"})
    assert "2026-06-03" in _rev(runner, "prod")


def test_audit_vetoes_bad_publish(runner):
    runner.run("prod")
    before = _rev(runner, "prod")
    runner.catalog.catalog.load_table("raw.orders").append(
        _orders([(9, 1, "2026-06-09", "paid", -1000.0)]))
    with pytest.raises(AuditError):
        runner.run("prod", select={"daily_revenue"}, force=True)
    assert _rev(runner, "prod") == before  # unchanged
    tbl = runner.catalog.catalog.load_table(runner.catalog.identifier("daily_revenue"))
    assert "wap" not in tbl.refs()  # staging branch cleaned up


def test_time_travel(runner):
    runner.run("prod")
    snaps = runner.catalog.history("customer_orders")
    assert len(snaps) >= 1
    first = snaps[0]["snapshot_id"]
    assert runner.catalog.scan_at("customer_orders", first).num_rows == 3
