"""Dependency graph over models and sources."""

from __future__ import annotations

from dataclasses import dataclass

from cleyrop_dm.config import ProjectConfig
from cleyrop_dm.model import Model


@dataclass
class ResolvedRef:
    """Where a model reference points."""

    name: str
    kind: str  # "model" | "source"
    identifier: str  # physical iceberg identifier for sources; model name otherwise


class Dag:
    """Builds and orders the model dependency graph.

    Each model's references are classified as either another *model* (an edge in
    the DAG) or an external *source*. Unknown references raise, which catches
    typos early -- the same guardrail dbt's ``ref``/``source`` gives you.
    """

    def __init__(self, models: dict[str, Model], project: ProjectConfig):
        self.models = models
        self.project = project
        self.edges: dict[str, set[str]] = {}          # model -> upstream models
        self.resolved: dict[str, dict[str, ResolvedRef]] = {}
        self._resolve()
        self._check_acyclic()

    def _resolve(self) -> None:
        source_names = set(self.project.sources)
        for name, model in self.models.items():
            upstream: set[str] = set()
            refmap: dict[str, ResolvedRef] = {}
            for ref in sorted(model.refs):
                if ref in self.models:
                    upstream.add(ref)
                    refmap[ref] = ResolvedRef(ref, "model", ref)
                elif ref in source_names:
                    src = self.project.sources[ref]
                    refmap[ref] = ResolvedRef(ref, "source", src.identifier)
                else:
                    raise ValueError(
                        f"Model {name!r} references {ref!r}, which is neither a "
                        f"known model nor a declared source."
                    )
            self.edges[name] = upstream
            self.resolved[name] = refmap

    def _check_acyclic(self) -> None:
        # Kahn's algorithm doubles as the topological sort and the cycle check.
        self.topo_order()

    def upstream(self, name: str) -> set[str]:
        return self.edges[name]

    def topo_order(self, selected: set[str] | None = None) -> list[str]:
        """Return models in dependency order (upstream before downstream).

        If ``selected`` is given, the order is restricted to those models plus
        the ancestors they depend on.
        """
        nodes = set(self.models) if selected is None else self._with_ancestors(selected)
        indeg = {n: len(self.edges[n] & nodes) for n in nodes}
        ready = sorted(n for n, d in indeg.items() if d == 0)
        order: list[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m in nodes:
                if n in self.edges[m]:
                    indeg[m] -= 1
                    if indeg[m] == 0:
                        ready.append(m)
                        ready.sort()
        if len(order) != len(nodes):
            cyclic = nodes - set(order)
            raise ValueError(f"Cycle detected among models: {sorted(cyclic)}")
        return order

    def _with_ancestors(self, selected: set[str]) -> set[str]:
        out: set[str] = set()
        stack = list(selected)
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(self.edges[n])
        return out
