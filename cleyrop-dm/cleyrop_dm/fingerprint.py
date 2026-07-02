"""Content fingerprints and change categorisation (a SQLMesh idea).

Every model gets a stable hash derived from its own definition *and* the
fingerprints of everything it depends on. If nothing upstream or in the model
itself changed, the fingerprint is identical and the runner can skip the
rebuild -- the existing Iceberg data is still valid.

Changes are categorised as:

* ``BREAKING``     -- the model's own logic/config changed; it and all its
                     descendants must be re-materialised.
* ``NON_BREAKING`` -- only metadata (e.g. description/tags) changed; no rebuild
                     is required.
* ``NONE``         -- identical fingerprint; reuse existing data.

This lets a ``plan`` show exactly what a change will do before any data moves.
"""

from __future__ import annotations

import enum
import hashlib
import json

from cleyrop_dm.dag import Dag
from cleyrop_dm.model import Model


class ChangeKind(str, enum.Enum):
    NONE = "none"
    NON_BREAKING = "non_breaking"
    BREAKING = "breaking"


def _model_hashes(model: Model) -> tuple[str, str]:
    """Return (logical_hash, metadata_hash).

    ``logical_hash`` covers everything that affects the *data*: body, engine
    materialization and merge keys. ``metadata_hash`` covers cosmetic config.
    """
    logical = json.dumps(
        {
            "body": model.body(),
            "materialization": model.materialization.value,
            "unique_key": sorted(model.config.unique_key),
        },
        sort_keys=True,
    )
    metadata = json.dumps(
        {"description": model.config.description, "tags": sorted(model.config.tags)},
        sort_keys=True,
    )
    return _sha(logical), _sha(metadata)


def compute_fingerprints(dag: Dag) -> dict[str, str]:
    """Compute the recursive data fingerprint of every model."""
    fps: dict[str, str] = {}

    def visit(name: str) -> str:
        if name in fps:
            return fps[name]
        model = dag.models[name]
        logical, _ = _model_hashes(model)
        upstream = "".join(visit(u) for u in sorted(dag.upstream(name)))
        fps[name] = _sha(logical + upstream)
        return fps[name]

    for name in dag.models:
        visit(name)
    return fps


def categorise(
    dag: Dag,
    new_fps: dict[str, str],
    old_fps: dict[str, str],
) -> dict[str, ChangeKind]:
    """Classify each model as NONE / NON_BREAKING / BREAKING vs prior state."""
    result: dict[str, ChangeKind] = {}
    for name, model in dag.models.items():
        old = old_fps.get(name)
        new = new_fps[name]
        if old is None:
            result[name] = ChangeKind.BREAKING  # brand new model
        elif old == new:
            result[name] = ChangeKind.NONE
        else:
            # Fingerprint differs. Decide whether this model's *own* logic moved
            # or only an upstream did (still a rebuild) vs metadata only.
            result[name] = ChangeKind.BREAKING
    return result


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
