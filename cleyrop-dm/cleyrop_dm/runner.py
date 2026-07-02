"""The runner: compute models and apply a plan under WAP semantics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from cleyrop_dm.audits import run_audits
from cleyrop_dm.catalog import IcebergCatalog, MaterializeResult
from cleyrop_dm.config import Materialization, ProjectConfig
from cleyrop_dm.dag import Dag
from cleyrop_dm.engines import get_engine
from cleyrop_dm.model import ExecutionContext, PythonModel, SqlModel, load_models
from cleyrop_dm.plan import Plan, build_plan
from cleyrop_dm.state import StateStore


@dataclass
class ApplyResult:
    env: str
    materialized: list[MaterializeResult]
    skipped: list[str]


class Runner:
    def __init__(self, project: ProjectConfig, state_path: str | Path | None = None):
        self.project = project
        self.models = load_models(project)
        self.dag = Dag(self.models, project)
        self.catalog = IcebergCatalog(project)
        self.engine = get_engine(project.engine, project.engine_config)
        state_path = state_path or (project.project_dir / ".cleyrop" / "state.db")
        Path(state_path).parent.mkdir(parents=True, exist_ok=True)
        self.state = StateStore(state_path)

    # ------------------------------------------------------------------ #
    # planning
    # ------------------------------------------------------------------ #
    def plan(self, env: str, select: set[str] | None = None, force: bool = False) -> Plan:
        old = self.state.fingerprints(env)
        return build_plan(self.dag, old, env, select, force)

    # ------------------------------------------------------------------ #
    # applying
    # ------------------------------------------------------------------ #
    def apply(self, plan: Plan) -> ApplyResult:
        env = plan.env
        cache: dict[str, pa.Table] = {}
        materialized: list[MaterializeResult] = []
        skipped: list[str] = []

        def resolve(name: str) -> pa.Table:
            """Return the Arrow data for an upstream model or source in ``env``."""
            if name in self.project.sources:
                return self.catalog.scan_source(self.project.sources[name].identifier)
            model = self.models[name]
            if model.materialization == Materialization.VIEW:
                if name not in cache:
                    cache[name] = self._compute(model, env, resolve)
                return cache[name]
            return self.catalog.scan_env(self.catalog.identifier(name), env)

        for name in plan.order:
            model = self.models[name]
            if model.materialization == Materialization.VIEW:
                # Ephemeral: never persisted, only recorded for state/lineage.
                self.state.record(env, name, plan.fingerprints[name], 0)
                skipped.append(name)
                continue

            data = self._compute(model, env, resolve)

            def _audit(staged: pa.Table, _m=model) -> None:
                run_audits(_m.name, _m.config.audits, staged)

            result = self.catalog.materialize(
                model_name=name,
                arrow=data,
                materialization=model.materialization,
                env=env,
                unique_key=model.config.unique_key,
                audit=_audit,
            )
            self.state.record(env, name, plan.fingerprints[name], result.snapshot_id)
            materialized.append(result)

        return ApplyResult(env=env, materialized=materialized, skipped=skipped)

    def run(self, env: str, select: set[str] | None = None, force: bool = False) -> ApplyResult:
        """Convenience: plan then apply."""
        return self.apply(self.plan(env, select, force))

    # ------------------------------------------------------------------ #
    # promotion / inspection
    # ------------------------------------------------------------------ #
    def promote(self, from_env: str, to_env: str, select: set[str] | None = None) -> None:
        """Blue/green promotion: fast-forward ``to_env`` to ``from_env`` per model."""
        names = select or set(self.models)
        for name in self.dag.topo_order(selected=names):
            if self.models[name].materialization == Materialization.VIEW:
                continue
            if not self.catalog.table_exists(name):
                continue
            snap = self.catalog.promote(name, from_env, to_env)
            fp = self.state.fingerprints(from_env).get(name)
            if fp:
                self.state.record(to_env, name, fp, snap)

    def _compute(self, model, env: str, resolve) -> pa.Table:
        relations = {ref: resolve(ref) for ref in model.refs}
        if isinstance(model, SqlModel):
            return self.engine.run_sql(model.body(), relations)
        if isinstance(model, PythonModel):
            ctx = ExecutionContext(engine=self.engine, _resolve=resolve)
            return model.execute(ctx)
        raise TypeError(f"Unknown model type: {type(model)}")

    def close(self) -> None:
        self.engine.close()
        self.state.close()
