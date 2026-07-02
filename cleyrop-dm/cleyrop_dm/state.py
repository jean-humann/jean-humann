"""Persistent state store.

Tracks, per environment, the fingerprint and published snapshot of every model.
This is what makes ``plan`` possible (diff the desired fingerprints against the
last applied ones) and gives an auditable history of what was deployed where --
important for a sovereign platform where every change must be accountable.

Backed by SQLite for the prototype; in production this would live alongside the
Iceberg catalog metadata (or in the catalog's own backing store).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelState:
    env: str
    model: str
    fingerprint: str
    snapshot_id: int
    updated_at: float


class StateStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._con = sqlite3.connect(self.path)
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS model_state (
                env TEXT NOT NULL,
                model TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                snapshot_id INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (env, model)
            )
            """
        )
        self._con.commit()

    def fingerprints(self, env: str) -> dict[str, str]:
        rows = self._con.execute(
            "SELECT model, fingerprint FROM model_state WHERE env = ?", (env,)
        ).fetchall()
        return {model: fp for model, fp in rows}

    def record(self, env: str, model: str, fingerprint: str, snapshot_id: int) -> None:
        self._con.execute(
            "INSERT INTO model_state (env, model, fingerprint, snapshot_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(env, model) DO UPDATE SET "
            "fingerprint=excluded.fingerprint, snapshot_id=excluded.snapshot_id, "
            "updated_at=excluded.updated_at",
            (env, model, fingerprint, snapshot_id, time.time()),
        )
        self._con.commit()

    def all(self, env: str) -> list[ModelState]:
        rows = self._con.execute(
            "SELECT env, model, fingerprint, snapshot_id, updated_at "
            "FROM model_state WHERE env = ? ORDER BY model",
            (env,),
        ).fetchall()
        return [ModelState(*r) for r in rows]

    def close(self) -> None:
        self._con.close()
