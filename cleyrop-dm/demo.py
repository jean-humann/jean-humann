#!/usr/bin/env python3
"""End-to-end, self-contained demo of cleyrop-dm.

Runs entirely locally against a fresh Iceberg warehouse (SQLite catalog + local
files) using the DuckDB engine. No cluster, no external services. It walks
through the full lifecycle:

    1. First production load   -- plan + apply, audits gate every table.
    2. Zero-copy dev branch    -- incremental run in `dev`, prod untouched (WAP).
    3. Blue/green promotion    -- fast-forward prod to dev.
    4. Audit veto              -- a bad row is written, audited, and rejected;
                                  prod never sees it.
    5. Time travel             -- read any previous Iceberg snapshot.

Run it:  python demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog

from cleyrop_dm.audits import AuditError
from cleyrop_dm.config import ProjectConfig
from cleyrop_dm.runner import Runner

HERE = Path(__file__).parent
PROJECT_DIR = HERE / "examples" / "retail"


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n {title}\n{'=' * 72}")


def seed_raw(catalog: SqlCatalog) -> None:
    """Create the external `raw` source tables the project reads."""
    catalog.create_namespace("raw")

    customers = pa.table(
        {
            "customer_id": pa.array([1, 2, 3, 4], pa.int64()),
            "name": ["Alice", "Bob", "Cleo", "Dan"],
            "country": ["FR", "DE", "FR", "US"],
        }
    )
    t = catalog.create_table("raw.customers", schema=customers.schema)
    t.append(customers)

    orders = _orders(
        [
            (101, 1, "2026-06-01", "paid", 50.0),
            (102, 1, "2026-06-02", "paid", 30.0),
            (103, 2, "2026-06-01", "new", 20.0),
            (104, 3, "2026-06-03", "paid", 120.0),
            (105, 3, "2026-06-03", "cancelled", 10.0),
            (106, 4, "2026-06-04", "paid", 80.0),
        ]
    )
    t = catalog.create_table("raw.orders", schema=orders.schema)
    t.append(orders)


def append_orders(catalog: SqlCatalog, rows: list[tuple]) -> None:
    catalog.load_table("raw.orders").append(_orders(rows))


def _orders(rows: list[tuple]) -> pa.Table:
    cols = list(zip(*rows))
    return pa.table(
        {
            "order_id": pa.array(cols[0], pa.int64()),
            "customer_id": pa.array(cols[1], pa.int64()),
            "order_ts": pa.array(cols[2], pa.string()),
            "status": pa.array(cols[3], pa.string()),
            "amount": pa.array(cols[4], pa.float64()),
        }
    )


def revenue_by_day(runner: Runner, env: str) -> dict:
    tbl = runner.catalog.scan_env(runner.catalog.identifier("daily_revenue"), env)
    d = tbl.to_pydict()
    return {str(k): v for k, v in zip(d["order_date"], d["revenue"])}


def main() -> None:
    warehouse = tempfile.mkdtemp(prefix="cleyrop_wh_")
    catalog_props = {
        "type": "sql",
        "uri": f"sqlite:///{warehouse}/catalog.db",
        "warehouse": f"file://{warehouse}",
    }

    # Point the (otherwise self-contained) project at this throwaway warehouse.
    project = ProjectConfig.load(PROJECT_DIR)
    project.catalog = dict(catalog_props)

    # Seed the external raw source tables.
    seed_raw(SqlCatalog("retail", **catalog_props))

    state_db = Path(warehouse) / "state.db"
    runner = Runner(project, state_path=state_db)

    rule("Models (topologically ordered)")
    for name in runner.dag.topo_order():
        m = runner.models[name]
        deps = ", ".join(sorted(runner.dag.upstream(name))) or "-"
        print(f"  {name:<20} {m.materialization.value:<12} deps: {deps}")

    # ------------------------------------------------------------------ #
    rule("1. First production load  (cleyrop-dm apply --env prod)")
    plan = runner.plan("prod")
    print(plan.describe())
    result = runner.apply(plan)
    for m in result.materialized:
        tag = "created" if m.created else ("WAP" if m.used_wap else "updated")
        print(f"  ✓ {m.model:<20} {m.rows:>3} rows  branch={m.branch:<8} [{tag}]")
    for s in result.skipped:
        print(f"  · {s:<20} (view — inlined, not materialised)")
    print("\n  prod daily_revenue:", revenue_by_day(runner, "prod"))

    # ------------------------------------------------------------------ #
    rule("2. Zero-copy dev branch + incremental run  (WAP, prod untouched)")
    append_orders(runner.catalog.catalog, [
        (107, 2, "2026-06-05", "paid", 200.0),
        (108, 1, "2026-06-05", "paid", 25.0),
    ])
    print("  Appended 2 new orders on 2026-06-05 to raw.orders.")
    # Incremental model: code unchanged, so force it to pick up new source rows.
    res = runner.run("dev", select={"daily_revenue"}, force=True)
    for m in res.materialized:
        tag = "created" if m.created else ("WAP" if m.used_wap else "updated")
        print(f"  ✓ {m.model:<20} {m.rows:>3} rows  branch={m.branch:<8} [{tag}]")

    tbl = runner.catalog.catalog.load_table(runner.catalog.identifier("daily_revenue"))
    print("  Iceberg refs on daily_revenue:", sorted(tbl.refs().keys()))
    print("  dev  daily_revenue:", revenue_by_day(runner, "dev"))
    print("  prod daily_revenue:", revenue_by_day(runner, "prod"), " <- unchanged")

    # ------------------------------------------------------------------ #
    rule("3. Blue/green promotion  (fast-forward prod -> dev)")
    runner.promote(from_env="dev", to_env="prod", select={"daily_revenue"})
    print("  prod daily_revenue:", revenue_by_day(runner, "prod"), " <- now promoted")

    # ------------------------------------------------------------------ #
    rule("4. Audit veto  (bad data is written, audited, rejected)")
    append_orders(runner.catalog.catalog, [
        (109, 4, "2026-06-06", "paid", -500.0),  # refund makes the day negative
    ])
    print("  Appended a -500 refund on 2026-06-06 (violates revenue >= 0).")
    before = revenue_by_day(runner, "prod")
    try:
        runner.run("prod", select={"daily_revenue"}, force=True)
        print("  !! ERROR: audit should have failed")
    except AuditError as e:
        print(f"  ✗ publish vetoed: {e}")
    after = revenue_by_day(runner, "prod")
    print(f"  prod unchanged after veto: {before == after}  ({sorted(after)})")
    tbl.refresh()
    print("  wap branch cleaned up:", "wap" not in tbl.refs())

    # ------------------------------------------------------------------ #
    rule("5. Time travel  (read any prior Iceberg snapshot)")
    snaps = runner.catalog.history("daily_revenue")
    print(f"  daily_revenue has {len(snaps)} snapshots on main.")
    first = snaps[0]["snapshot_id"]
    past = runner.catalog.scan_at("daily_revenue", first).num_rows
    now = runner.catalog.scan_env(runner.catalog.identifier("daily_revenue"), "prod").num_rows
    print(f"  first snapshot: {past} day(s)   current: {now} day(s)")

    runner.close()
    print("\nDone. Warehouse:", warehouse)


if __name__ == "__main__":
    main()
