"""Data audits (dbt calls them *tests*).

Audits are assertions evaluated against a model's freshly-written data *inside*
the WAP branch, before it is published. A failing audit vetoes the publish, so
bad data never becomes visible in an environment.

Specs are written in the model header, e.g.::

    -- @audits: not_null(order_id), unique(order_id), accepted_values(status, 'new', 'paid')

Built-in checks: ``not_null``, ``unique``, ``accepted_values``,
``row_count_at_least``, ``expression``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb
import pyarrow as pa

_SPEC_RE = re.compile(r"^(\w+)\s*\((.*)\)\s*$")


@dataclass
class CheckResult:
    spec: str
    passed: bool
    violations: int
    detail: str = ""


class AuditError(Exception):
    def __init__(self, model: str, failures: list[CheckResult]):
        self.model = model
        self.failures = failures
        msg = "; ".join(f"{f.spec}: {f.violations} violation(s)" for f in failures)
        super().__init__(f"Audit failed for {model!r}: {msg}")


def run_audits(model_name: str, specs: list[str], data: pa.Table) -> list[CheckResult]:
    """Evaluate all audit specs; raise :class:`AuditError` if any fail."""
    con = duckdb.connect()
    con.register("_audit_t", data)
    results: list[CheckResult] = []
    for spec in specs:
        results.append(_run_one(con, spec))
    con.close()
    failures = [r for r in results if not r.passed]
    if failures:
        raise AuditError(model_name, failures)
    return results


def _run_one(con: duckdb.DuckDBPyConnection, spec: str) -> CheckResult:
    m = _SPEC_RE.match(spec.strip())
    if not m:
        raise ValueError(f"Cannot parse audit spec: {spec!r}")
    fn, raw_args = m.group(1), m.group(2)
    args = [a.strip() for a in raw_args.split(",")] if raw_args.strip() else []
    violations, detail = _CHECKS[fn](con, args)
    return CheckResult(spec=spec, passed=violations == 0, violations=violations, detail=detail)


def _count(con, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def _not_null(con, args):
    (col,) = args
    n = _count(con, f"SELECT count(*) FROM _audit_t WHERE {col} IS NULL")
    return n, f"{col} has nulls" if n else ""


def _unique(con, args):
    cols = ", ".join(args)
    n = _count(
        con,
        f"SELECT coalesce(sum(c - 1), 0) FROM "
        f"(SELECT count(*) c FROM _audit_t GROUP BY {cols} HAVING count(*) > 1)",
    )
    return n, f"duplicate ({cols})" if n else ""


def _accepted_values(con, args):
    col, values = args[0], args[1:]
    in_list = ", ".join(values)
    n = _count(con, f"SELECT count(*) FROM _audit_t WHERE {col} NOT IN ({in_list})")
    return n, f"{col} outside accepted set" if n else ""


def _row_count_at_least(con, args):
    (n_min,) = args
    total = _count(con, "SELECT count(*) FROM _audit_t")
    ok = total >= int(n_min)
    return (0 if ok else 1), "" if ok else f"row_count {total} < {n_min}"


def _expression(con, args):
    expr = ", ".join(args)  # allow commas inside the expression
    n = _count(con, f"SELECT count(*) FROM _audit_t WHERE NOT ({expr})")
    return n, f"expression violated: {expr}" if n else ""


_CHECKS = {
    "not_null": _not_null,
    "unique": _unique,
    "accepted_values": _accepted_values,
    "row_count_at_least": _row_count_at_least,
    "expression": _expression,
}
