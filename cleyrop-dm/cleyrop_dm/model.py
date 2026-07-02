"""Model definitions and loading.

A *model* is a single Cleyrop dataset: a named node that produces an Arrow
table when executed. Two flavours are supported:

* :class:`SqlModel`   -- a ``SELECT`` statement plus a ``-- @key: value`` header.
                         Dependencies are inferred from the SQL with SQLGlot, so
                         no ``ref()`` macros or Jinja are required.
* :class:`PythonModel` -- a Python module exposing ``META`` and a
                         ``model(ctx)`` function returning a ``pa.Table``. Use it
                         for ML feature engineering or anything awkward in SQL.
"""

from __future__ import annotations

import importlib.util
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pyarrow as pa
import sqlglot
from sqlglot import exp

from cleyrop_dm.config import Materialization, ModelConfig, ProjectConfig

if TYPE_CHECKING:  # pragma: no cover
    from cleyrop_dm.engines.base import Engine

# ``-- @key: value`` header lines at the top of a SQL model file.
_HEADER_RE = re.compile(r"^\s*--\s*@(\w+)\s*:\s*(.*?)\s*$")


class Model(ABC):
    """Common interface shared by SQL and Python models."""

    config: ModelConfig
    path: Path
    #: Table/source names this model reads. Resolved against models + sources.
    refs: set[str]

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def materialization(self) -> Materialization:
        return self.config.materialization

    @abstractmethod
    def body(self) -> str:
        """Return the canonical body used for fingerprinting (SQL text / source)."""

    @abstractmethod
    def execute(self, ctx: "ExecutionContext") -> pa.Table:
        """Compute and return the model's output as an Arrow table."""


@dataclass
class ExecutionContext:
    """Passed to a model at execution time.

    ``ref(name)`` returns the Arrow table of an upstream model or source, read
    from the environment currently being built. ``engine`` is the active engine
    so Python models can push compute down if they wish.
    """

    engine: "Engine"
    _resolve: Callable[[str], pa.Table]

    def ref(self, name: str) -> pa.Table:
        return self._resolve(name)


class SqlModel(Model):
    def __init__(self, path: Path, project: ProjectConfig):
        self.path = path
        self._project = project
        text = path.read_text()
        self._header, self._sql = _split_header(text)
        name = self._header.get("model") or path.stem
        self.config = ModelConfig(
            name=name,
            materialization=Materialization(
                self._header.get("materialization", "table")
            ),
            unique_key=_split_list(self._header.get("unique_key", "")),
            audits=_split_audits(self._header.get("audits", "")),
            description=self._header.get("description", ""),
            tags=_split_list(self._header.get("tags", "")),
        )
        self.refs = _extract_table_refs(self._sql)

    def body(self) -> str:
        return self._sql.strip()

    def rendered_sql(self, relation_map: dict[str, str]) -> str:
        """Rewrite bare table references to their physical/registered relations.

        ``relation_map`` maps a logical name (model or source) to the identifier
        the engine should read (e.g. a registered Arrow view name, or a
        catalog-qualified Iceberg table). References not in the map are left
        untouched.
        """
        tree = sqlglot.parse_one(self._sql, read="duckdb")
        for table in tree.find_all(exp.Table):
            if table.name in relation_map and not table.db:
                table.set("this", exp.to_identifier(relation_map[table.name]))
        return tree.sql(dialect="duckdb")

    def execute(self, ctx: ExecutionContext) -> pa.Table:  # pragma: no cover
        # SQL models are executed by the runner via the engine, which needs the
        # rendered SQL and the resolved upstream relations. This method exists to
        # satisfy the interface; the runner calls the engine directly.
        raise NotImplementedError("SQL models are executed by the engine")


class PythonModel(Model):
    def __init__(self, path: Path, project: ProjectConfig):
        self.path = path
        self._project = project
        spec = importlib.util.spec_from_file_location(f"cleyrop_model_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        meta = getattr(module, "META", {})
        self._fn = getattr(module, "model")
        self.config = ModelConfig(
            name=meta.get("name", path.stem),
            materialization=Materialization(meta.get("materialization", "table")),
            unique_key=list(meta.get("unique_key", [])),
            depends_on=list(meta.get("depends_on", [])),
            audits=list(meta.get("audits", [])),
            description=meta.get("description", ""),
            tags=list(meta.get("tags", [])),
        )
        self.refs = set(self.config.depends_on)
        self._source = path.read_text()

    def body(self) -> str:
        return self._source.strip()

    def execute(self, ctx: ExecutionContext) -> pa.Table:
        return self._fn(ctx)


def load_models(project: ProjectConfig) -> dict[str, Model]:
    """Discover and load every model under the project's ``model_paths``."""
    models: dict[str, Model] = {}
    for rel in project.model_paths:
        root = project.project_dir / rel
        for path in sorted(root.rglob("*")):
            if path.suffix == ".sql":
                model: Model = SqlModel(path, project)
            elif path.suffix == ".py" and not path.name.startswith("_"):
                model = PythonModel(path, project)
            else:
                continue
            if model.name in models:
                raise ValueError(f"Duplicate model name: {model.name!r}")
            models[model.name] = model
    return models


# --------------------------------------------------------------------------- #
# Header / dependency parsing helpers
# --------------------------------------------------------------------------- #
def _split_header(text: str) -> tuple[dict[str, str], str]:
    """Parse the leading ``-- @key: value`` header block.

    The header is the contiguous run of leading blank / ``--`` comment lines. A
    comment line that is not ``@key: value`` is treated as a continuation of the
    previous key (so multi-line descriptions work). The header ends at the first
    line that is neither blank nor a comment -- i.e. the start of the SQL.
    """
    header: dict[str, str] = {}
    body_lines: list[str] = []
    last_key: str | None = None
    in_header = True
    for line in text.splitlines():
        if in_header:
            stripped = line.strip()
            if stripped == "":
                continue  # blank lines don't end the header
            if stripped.startswith("--"):
                m = _HEADER_RE.match(line)
                if m:
                    last_key = m.group(1).lower()
                    header[last_key] = m.group(2)
                elif last_key is not None:
                    header[last_key] += " " + stripped.lstrip("-").strip()
                continue
            in_header = False
        body_lines.append(line)
    return header, "\n".join(body_lines)


def _split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _split_audits(value: str) -> list[str]:
    # Audits look like "not_null(order_id), unique(order_id, day)"; split on
    # top-level commas only so args stay grouped.
    out, depth, cur = [], 0, ""
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _extract_table_refs(sql: str) -> set[str]:
    """Return the set of bare table names referenced by a query.

    CTE names defined in the same query are excluded so they are not mistaken
    for upstream models.
    """
    tree = sqlglot.parse_one(sql, read="duckdb")
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    refs: set[str] = set()
    for table in tree.find_all(exp.Table):
        # Only consider unqualified single-part identifiers as candidate refs.
        if table.db or table.catalog:
            continue
        if table.name and table.name not in cte_names:
            refs.add(table.name)
    return refs
