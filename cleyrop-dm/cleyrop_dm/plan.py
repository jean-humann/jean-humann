"""Plan: decide what a change will do, before any data moves."""

from __future__ import annotations

from dataclasses import dataclass, field

from cleyrop_dm.dag import Dag
from cleyrop_dm.fingerprint import ChangeKind, compute_fingerprints


@dataclass
class Plan:
    env: str
    fingerprints: dict[str, str]
    changes: dict[str, ChangeKind]
    order: list[str]  # models to (re)build, in dependency order
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.order)

    def describe(self) -> str:
        lines = [f"Plan for environment '{self.env}':"]
        if not self.order:
            lines.append("  (no changes -- everything is up to date)")
        for name in self.order:
            kind = self.changes[name].value
            lines.append(f"  ~ {name:<28} [{kind}]")
        if self.unchanged:
            lines.append(f"  = {len(self.unchanged)} model(s) unchanged, reusing data")
        return "\n".join(lines)


def build_plan(
    dag: Dag,
    old_fingerprints: dict[str, str],
    env: str,
    select: set[str] | None = None,
    force: bool = False,
) -> Plan:
    """Compare desired vs applied fingerprints and produce an ordered plan.

    Because fingerprints are recursive, changing one model automatically dirties
    all of its descendants -- they fall out of the diff without special-casing.

    ``force`` runs the selected models even when their fingerprint is unchanged.
    This is how incremental models pick up new source rows on a schedule: their
    code hasn't changed, but they still need to run.
    """
    desired = compute_fingerprints(dag)
    if force:
        base = set(select) if select else set(dag.models)
        dirty = set(dag.topo_order(selected=base))
    else:
        dirty = {
            name for name, fp in desired.items() if old_fingerprints.get(name) != fp
        }
        if select is not None:
            # Restrict to the selection and its ancestors, intersected with dirty.
            scope = set(dag.topo_order(selected=select))
            dirty &= scope
    order = dag.topo_order(selected=dirty) if dirty else []
    changes = {
        name: (ChangeKind.BREAKING if name in dirty else ChangeKind.NONE)
        for name in dag.models
    }
    unchanged = [n for n in dag.models if n not in dirty]
    return Plan(env=env, fingerprints=desired, changes=changes, order=order, unchanged=unchanged)
