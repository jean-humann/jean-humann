#!/usr/bin/env python3
"""Reproduce four prototype gaps using synthetic, disposable local data.

Run with the interpreter where cleyrop-dm, pyarrow and pytest are installed.
An exit status of zero means the counterexamples reproduced, not that Hemera
met its product guarantees. The installed package is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa

from cleyrop_dm.audits import AuditError
from cleyrop_dm.catalog import IcebergCatalog
from cleyrop_dm.config import Materialization, ProjectConfig
from cleyrop_dm.runner import Runner


def project(root: Path, name: str) -> ProjectConfig:
    root.mkdir(parents=True, exist_ok=True)
    (root / "models").mkdir(exist_ok=True)
    return ProjectConfig(
        name=name,
        namespace="synthetic",
        project_dir=root,
        catalog={
            "type": "sql",
            "uri": f"sqlite:///{root / 'catalog.db'}",
            "warehouse": (root / "warehouse").as_uri(),
        },
    )


def data(value: int) -> pa.Table:
    return pa.table({"value": pa.array([value], type=pa.int64())})


def write(cat: IcebergCatalog, value: int, env: str = "prod"):
    return cat.materialize("example", data(value), Materialization.TABLE,
                           env, [], lambda staged: None)


def seed_veto(root: Path) -> dict:
    class SyntheticVeto(Exception):
        pass

    config = project(root, "seed_probe")
    writer, reader = IcebergCatalog(config), IcebergCatalog(config)
    observed = {}

    def veto(staged):
        observed["rows_read_on_main_before_veto"] = reader.scan_env(
            "synthetic.example", "prod").to_pylist()
        observed["table_listed_before_veto"] = reader.table_exists("example")
        raise SyntheticVeto("Synthetic veto")

    try:
        writer.materialize("example", data(-1), Materialization.TABLE,
                           "prod", [], veto)
    except SyntheticVeto:
        observed["veto_raised"] = True
    observed["table_exists_after_veto"] = reader.table_exists("example")
    assert observed["rows_read_on_main_before_veto"] == [{"value": -1}]
    assert observed["table_listed_before_veto"]
    assert observed["veto_raised"] and not observed["table_exists_after_veto"]
    return observed


def divergent_promotion(root: Path) -> dict:
    cat = IcebergCatalog(project(root, "promotion_probe"))
    initial = write(cat, 0).snapshot_id
    dev = write(cat, 1, "dev").snapshot_id
    prod = write(cat, 2).snapshot_id
    table = cat.catalog.load_table("synthetic.example")
    ancestors = set()
    cursor = table.snapshot_by_id(dev)
    while cursor is not None:
        ancestors.add(cursor.snapshot_id)
        cursor = (table.snapshot_by_id(cursor.parent_snapshot_id)
                  if cursor.parent_snapshot_id else None)
    assert initial in ancestors and prod not in ancestors
    before = cat.scan_env("synthetic.example", "prod").to_pylist()
    result = cat.promote("example", "dev", "prod")
    after = cat.scan_env("synthetic.example", "prod").to_pylist()
    assert result == dev and before == [{"value": 2}]
    assert after == [{"value": 1}]
    return {"initial_snapshot": initial, "dev_snapshot": dev,
            "advanced_prod_snapshot": prod, "target_is_ancestor_of_dev": False,
            "promotion_rejected": False, "prod_before": before,
            "prod_after": after}


def audit_and_cache(root: Path) -> dict:
    config = project(root, "audit_probe")
    model = root / "models" / "example.sql"
    model.write_text("-- @model: example\n-- @audits: row_count_at_least(1)\nSELECT 1::BIGINT AS value\n")
    state_path = root / "state.db"
    runner = Runner(config, state_path=state_path)
    try:
        runner.run("prod")
        assert not runner.plan("prod").has_changes
        original = runner.plan("prod").fingerprints["example"]
        snapshot = runner.catalog.catalog.load_table("synthetic.example").current_snapshot()
        properties = dict(snapshot.summary.additional_properties)
    finally:
        runner.close()
    model.write_text("-- @model: example\n-- @audits: row_count_at_least(2)\nSELECT 1::BIGINT AS value\n")
    runner = Runner(config, state_path=state_path)
    try:
        plan = runner.plan("prod")
        assert not plan.has_changes and plan.fingerprints["example"] == original
        forced_veto = False
        try:
            runner.run("prod", force=True)
        except AuditError:
            forced_veto = True
        assert forced_veto
    finally:
        runner.close()
    rebuilt = Runner(config, state_path=root / "fresh-state.db")
    try:
        empty_cache_plan = rebuilt.plan("prod")
        assert empty_cache_plan.has_changes
    finally:
        rebuilt.close()
    origin_keys = sorted(key for key in properties if key.startswith("origin."))
    assert not origin_keys
    return {"audit_changed_from": "row_count_at_least(1)",
            "audit_changed_to": "row_count_at_least(2)",
            "fingerprint_unchanged": True, "ordinary_plan_has_changes": False,
            "forced_execution_vetoed": forced_veto,
            "fresh_state_requests_rebuild": True, "published_origin_keys": origin_keys}


def plan_import_effect(root: Path) -> dict:
    config = project(root, "import_probe")
    marker = root / "plan-created-this.txt"
    (root / "models" / "example.py").write_text(
        "from pathlib import Path\n"
        "import pyarrow as pa\n"
        "Path(__file__).parent.parent.joinpath('plan-created-this.txt').write_text('synthetic import effect')\n"
        "META = {'name': 'example'}\n"
        "def model(ctx):\n"
        "    raise RuntimeError('The model function must not execute during planning')\n"
    )
    assert not marker.exists()
    runner = Runner(config, state_path=root / "state.db")
    try:
        at_initialization = marker.exists()
        plan = runner.plan("prod")
        assert at_initialization and plan.has_changes
        assert marker.read_text() == "synthetic import effect"
    finally:
        runner.close()
    return {"marker_exists_before_runner": False,
            "marker_exists_after_runner_initialization": at_initialization,
            "plan_completed_without_apply": True, "model_function_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("counteraudit-results.json"))
    parser.add_argument("--workdir", type=Path, default=None,
                        help="Parent for disposable run directory; it is removed afterwards")
    args = parser.parse_args()
    results = []
    probes = [("C1_initial_veto_visibility", seed_veto),
              ("C2_divergent_promotion", divergent_promotion),
              ("C3_audit_fingerprint_and_cache", audit_and_cache),
              ("C4_plan_import_effect", plan_import_effect)]
    with tempfile.TemporaryDirectory(prefix="hemera-counteraudit-", dir=args.workdir) as directory:
        for name, probe in probes:
            evidence = probe(Path(directory) / name)
            results.append({"probe": name, "assertion": "counterexample_reproduced",
                            "product_guarantee": "FAIL", "evidence": evidence})
    source = Path(inspect.getfile(IcebergCatalog))
    output = {
        "scope": "Unmodified cleyrop-dm prototype, local SQLite Iceberg catalog, synthetic data only",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "reference_commit": "1ca3659bc2a5c68cb4c38a7651bbd2a49808dad2",
        "catalog_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "versions": {name: importlib.metadata.version(name)
                     for name in ("pyiceberg", "pyarrow", "duckdb", "sqlglot")},
        "probes_reproduced": len(results), "product_guarantees_passed": 0,
        "interpretation": "Successful execution means the four counterexamples reproduced. It is not a passing product test.",
        "results": results,
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"probes_reproduced": len(results), "product_guarantees_passed": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
