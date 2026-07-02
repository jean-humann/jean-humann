"""Iceberg catalog wrapper: environments, Write-Audit-Publish and time travel.

This module is where cleyrop-dm leans on Iceberg's native features instead of
re-implementing them:

* **Environments** are Iceberg *branches*. ``prod`` is the ``main`` branch; every
  other environment (``dev``, a feature branch, ...) is a branch created off
  ``main`` -- zero-copy and instantly created.
* **Write-Audit-Publish** uses a short-lived ``wap`` branch: data is written and
  audited in isolation, then the environment branch is fast-forwarded to it only
  if the audits pass. Readers never observe partial or bad data.
* **Time travel** is just an Iceberg snapshot scan -- every apply is reversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pyarrow as pa
from pyiceberg.catalog import load_catalog

from cleyrop_dm.config import Materialization, ProjectConfig

PROD_ENV = "prod"
WAP_BRANCH = "wap"


@dataclass
class MaterializeResult:
    model: str
    env: str
    branch: str
    snapshot_id: int
    rows: int
    used_wap: bool
    created: bool


class IcebergCatalog:
    def __init__(self, project: ProjectConfig):
        self.project = project
        self.namespace = project.namespace
        props = dict(project.catalog)
        cat_name = props.pop("name", project.name)
        self.catalog = load_catalog(cat_name, **props)
        self._ensure_namespace()

    # ------------------------------------------------------------------ #
    # naming
    # ------------------------------------------------------------------ #
    def identifier(self, model_name: str) -> str:
        return f"{self.namespace}.{model_name}"

    @staticmethod
    def branch_for_env(env: str) -> str:
        return "main" if env == PROD_ENV else f"env_{env}"

    # ------------------------------------------------------------------ #
    # reads
    # ------------------------------------------------------------------ #
    def table_exists(self, model_name: str) -> bool:
        return self.catalog.table_exists(self.identifier(model_name))

    def scan_env(self, identifier: str, env: str) -> pa.Table:
        """Scan a managed table (or external source) as seen by ``env``."""
        tbl = self.catalog.load_table(identifier)
        branch = self.branch_for_env(env)
        snap = tbl.snapshot_by_name(branch) if branch != "main" else tbl.current_snapshot()
        if snap is None:  # env branch absent -> fall back to main/prod
            snap = tbl.current_snapshot()
        if snap is None:  # brand new empty table
            return tbl.scan().to_arrow()
        return tbl.scan(snapshot_id=snap.snapshot_id).to_arrow()

    def scan_source(self, identifier: str) -> pa.Table:
        return self.catalog.load_table(identifier).scan().to_arrow()

    def history(self, model_name: str) -> list[dict]:
        tbl = self.catalog.load_table(self.identifier(model_name))
        return [
            {"snapshot_id": s.snapshot_id, "timestamp_ms": s.timestamp_ms,
             "operation": s.summary.operation.value if s.summary else "?"}
            for s in tbl.snapshots()
        ]

    def scan_at(self, model_name: str, snapshot_id: int) -> pa.Table:
        """Time travel: read a managed table at an arbitrary snapshot."""
        tbl = self.catalog.load_table(self.identifier(model_name))
        return tbl.scan(snapshot_id=snapshot_id).to_arrow()

    # ------------------------------------------------------------------ #
    # write-audit-publish
    # ------------------------------------------------------------------ #
    def materialize(
        self,
        model_name: str,
        arrow: pa.Table,
        materialization: Materialization,
        env: str,
        unique_key: list[str],
        audit: Callable[[pa.Table], None],
    ) -> MaterializeResult:
        """Write ``arrow`` for ``model_name`` into ``env`` under WAP semantics.

        ``audit`` is called with the resulting Arrow data *before* publication;
        it must raise to veto the publish. On veto, no environment branch moves.
        """
        ident = self.identifier(model_name)
        env_branch = self.branch_for_env(env)

        if not self.catalog.table_exists(ident):
            return self._seed(model_name, ident, arrow, env, env_branch, audit)

        tbl = self.catalog.load_table(ident)
        self._ensure_env_branch(tbl, env_branch)

        # 1. WRITE -- branch off the environment head into an isolated wap branch.
        tbl.refresh()
        env_head = tbl.snapshot_by_name(env_branch)
        self._drop_branch_if_exists(tbl, WAP_BRANCH)
        tbl.manage_snapshots().create_branch(env_head.snapshot_id, WAP_BRANCH).commit()

        if materialization == Materialization.INCREMENTAL and unique_key:
            tbl.upsert(arrow, join_cols=unique_key, branch=WAP_BRANCH)
        else:
            tbl.overwrite(arrow, branch=WAP_BRANCH)

        tbl.refresh()
        wap_head = tbl.snapshot_by_name(WAP_BRANCH)
        staged = tbl.scan(snapshot_id=wap_head.snapshot_id).to_arrow()

        # 2. AUDIT -- veto by exception leaves the environment untouched.
        try:
            audit(staged)
        except Exception:
            self._drop_branch_if_exists(tbl, WAP_BRANCH)
            raise

        # 3. PUBLISH -- fast-forward the environment branch, drop the wap branch.
        self._point_branch_at(tbl, env_branch, wap_head.snapshot_id)
        self._drop_branch_if_exists(tbl, WAP_BRANCH)
        tbl.refresh()
        head = tbl.snapshot_by_name(env_branch)
        return MaterializeResult(
            model=model_name, env=env, branch=env_branch,
            snapshot_id=head.snapshot_id, rows=staged.num_rows,
            used_wap=True, created=False,
        )

    def promote(self, model_name: str, from_env: str, to_env: str) -> int:
        """Fast-forward ``to_env`` to the current head of ``from_env`` (blue/green)."""
        tbl = self.catalog.load_table(self.identifier(model_name))
        src = tbl.snapshot_by_name(self.branch_for_env(from_env))
        self._point_branch_at(tbl, self.branch_for_env(to_env), src.snapshot_id)
        tbl.refresh()
        return src.snapshot_id

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _seed(self, model_name, ident, arrow, env, env_branch, audit) -> MaterializeResult:
        """First-ever materialisation of a table: create + write on main, audit,
        then branch for non-prod environments."""
        tbl = self.catalog.create_table(ident, schema=arrow.schema)
        tbl.append(arrow)  # snapshot S0 on main
        tbl.refresh()
        staged = tbl.scan().to_arrow()
        try:
            audit(staged)
        except Exception:
            self.catalog.drop_table(ident)  # nothing published; discard the table
            raise
        if env_branch != "main":
            head = tbl.current_snapshot()
            tbl.manage_snapshots().create_branch(head.snapshot_id, env_branch).commit()
            tbl.refresh()
        head = tbl.snapshot_by_name(env_branch)
        return MaterializeResult(
            model=model_name, env=env, branch=env_branch,
            snapshot_id=head.snapshot_id, rows=staged.num_rows,
            used_wap=False, created=True,
        )

    def _ensure_env_branch(self, tbl, env_branch: str) -> None:
        if env_branch == "main":
            return
        tbl.refresh()
        if env_branch not in tbl.refs():
            main_head = tbl.current_snapshot()
            tbl.manage_snapshots().create_branch(main_head.snapshot_id, env_branch).commit()
            tbl.refresh()

    def _point_branch_at(self, tbl, branch: str, snapshot_id: int) -> None:
        """Move ``branch`` to ``snapshot_id`` using the available primitives."""
        if branch == "main":
            tbl.manage_snapshots().set_current_snapshot(snapshot_id=snapshot_id).commit()
        else:
            # No direct "set branch"; drop and recreate the ref at the target.
            self._drop_branch_if_exists(tbl, branch)
            tbl.manage_snapshots().create_branch(snapshot_id, branch).commit()
        tbl.refresh()

    def _drop_branch_if_exists(self, tbl, branch: str) -> None:
        tbl.refresh()
        if branch in tbl.refs():
            tbl.manage_snapshots().remove_branch(branch).commit()
            tbl.refresh()

    def _ensure_namespace(self) -> None:
        try:
            self.catalog.create_namespace(self.namespace)
        except Exception:
            pass  # already exists
