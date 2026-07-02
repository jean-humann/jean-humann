"""Project- and model-level configuration objects."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class Materialization(str, enum.Enum):
    """How a model's result is persisted into the Iceberg lakehouse.

    ``TABLE``       full refresh -- the model is rebuilt from scratch and the
                    result atomically replaces the published table.
    ``INCREMENTAL`` the model output is merged into the existing table using an
                    Iceberg row-level ``upsert`` on ``unique_key``.
    ``VIEW``        the model is not materialised; it is inlined into downstream
                    models as a CTE (a.k.a. dbt's ``ephemeral``). Useful for
                    lightweight staging logic you do not want to persist.
    """

    TABLE = "table"
    INCREMENTAL = "incremental"
    VIEW = "view"


@dataclass
class ModelConfig:
    """Per-model configuration.

    For SQL models this is parsed from a leading ``-- @key: value`` header
    (SQLMesh-style, no Jinja required). For Python models it comes from the
    module-level ``META`` dict.
    """

    name: str
    materialization: Materialization = Materialization.TABLE
    unique_key: list[str] = field(default_factory=list)
    # Human-declared upstream dependencies (Python models); SQL deps are
    # inferred automatically from the query with SQLGlot.
    depends_on: list[str] = field(default_factory=list)
    # Audit specs, e.g. ["not_null(order_id)", "unique(order_id)"].
    audits: list[str] = field(default_factory=list)
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.materialization, str):
            self.materialization = Materialization(self.materialization)


@dataclass
class Source:
    """An externally-managed Iceberg table the project reads but does not build."""

    name: str            # logical name used inside model SQL (e.g. ``raw_orders``)
    identifier: str      # physical catalog identifier (e.g. ``raw.orders``)
    description: str = ""


@dataclass
class ProjectConfig:
    """Top-level project settings, loaded from ``cleyrop_project.yml``."""

    name: str
    # The Iceberg namespace the project's managed tables live in.
    namespace: str = "analytics"
    # Default execution engine: "duckdb" | "spark_connect".
    engine: str = "duckdb"
    # PyIceberg catalog connection properties.
    catalog: dict[str, Any] = field(default_factory=dict)
    # Engine-specific connection properties (e.g. Spark Connect remote URL).
    engine_config: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Source] = field(default_factory=dict)
    model_paths: list[str] = field(default_factory=lambda: ["models"])
    project_dir: Path = field(default_factory=Path)

    @classmethod
    def load(cls, project_dir: str | Path) -> "ProjectConfig":
        project_dir = Path(project_dir)
        raw = yaml.safe_load((project_dir / "cleyrop_project.yml").read_text())
        sources = {
            s["name"]: Source(
                name=s["name"],
                identifier=s["identifier"],
                description=s.get("description", ""),
            )
            for s in raw.get("sources", [])
        }
        return cls(
            name=raw["name"],
            namespace=raw.get("namespace", "analytics"),
            engine=raw.get("engine", "duckdb"),
            catalog=raw.get("catalog", {}),
            engine_config=raw.get("engine_config", {}),
            sources=sources,
            model_paths=raw.get("model_paths", ["models"]),
            project_dir=project_dir,
        )
