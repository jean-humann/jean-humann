# Managing Cleyrop datasets on Iceberg — design

> How to manage Cleyrop datasets (Apache Iceberg tables) *properly* with Python
> and SQL transformations, taking the good ideas from **dbt-core** and
> **SQLMesh** and making them native to the Iceberg table format.

This document is the reasoning behind `cleyrop-dm`. The companion code is a
working reference implementation: `python demo.py` runs the whole lifecycle
end-to-end on a local Iceberg warehouse, and `pytest -q` proves the guarantees.

---

## 1. The problem

Cleyrop runs a **sovereign lakehouse**: data lives in Apache Iceberg tables in
object storage the customer controls, behind a catalog (REST / Nessie / Polaris
/ Glue), queried by several engines. We need to *manage the datasets* on top of
that lake — the derived tables analysts and ML depend on — with the same rigour
software gets:

1. **Declarative** — a dataset is defined once, in SQL or Python; the framework
   figures out order, dependencies and rebuilds.
2. **Safe to change** — you can see what a change will do *before* it runs, and a
   bad change never corrupts what's live.
3. **Testable & governed** — data quality is asserted before publication; every
   change is attributable and reversible. Non-negotiable for a sovereign
   platform.
4. **Engine-flexible** — the same transformation runs on DuckDB locally and on a
   Spark cluster in production, over the *one* Iceberg catalog. Cleyrop's stack
   is **Spark Connect / PyIceberg / DuckDB**.

Two tools already solve most of this for warehouses. Neither was built for an
Iceberg-first, multi-engine, sovereign lake. The right answer borrows heavily
from both and leans on Iceberg for the parts they simulate in software.

## 2. What dbt and SQLMesh get right (and wrong for us)

| Dimension | **dbt-core** | **SQLMesh** | What we want |
|---|---|---|---|
| Model definition | SQL + **Jinja** macros | SQL (parsed with **SQLGlot**) + **Python** models | SQL *and* first-class Python, **no Jinja** |
| Dependencies | explicit `{{ ref() }}` / `{{ source() }}` | inferred from parsed SQL | inferred from SQL (SQLGlot), explicit for Python |
| Change detection | none — you rebuild | **fingerprints** + breaking/non-breaking categorisation | fingerprints; skip unchanged models |
| Environments | separate target schemas, **full recompute** | **virtual environments** — dev reuses prod tables via view swaps | virtual envs, but **zero-copy at the table-format layer** |
| Safe deploy | `--defer`, manual blue/green | **virtual layer** promotion (swap views) | atomic promotion, native to Iceberg |
| Tests / audits | `tests/` run *after* build | **audits** + blocking runs | audits run **before publish** (WAP) |
| Time travel / rollback | — | snapshot-ish via state | native **Iceberg snapshots** |
| State | run artifacts | dedicated state DB | state DB for `plan`, catalog for data |

**dbt's** weak spots for us: Jinja string-templating instead of understanding
SQL; no change-awareness (every `dbt run` rebuilds); environments are physically
separate schemas (expensive full copies); tests run after data is already
written.

**SQLMesh's** great ideas — fingerprints, virtual environments, blocking audits,
plan/apply — are implemented *in the framework* on top of whatever warehouse it
targets. Its "virtual environment" is a layer of **views** that point at
physically named tables. That's clever, but it's a software re-implementation of
something **Iceberg already does at the storage layer**.

## 3. The key insight: Iceberg already has the hard parts

Iceberg is not just a file layout — it's a versioned, branchable, ACID table
format. Three native features map exactly onto what dbt/SQLMesh emulate:

| We need… | SQLMesh does… | Iceberg gives us… |
|---|---|---|
| Isolated environments | a view layer over hash-named tables | **branches** (`main`, `env_dev`, …) — zero-copy, instant |
| Safe deploy of new data | swap views atomically | **Write-Audit-Publish**: write to a branch, audit, fast-forward ref |
| Rollback / history | reconstruct from state | **snapshots** + `rollback_to_snapshot`, scan `snapshot_id` |
| Schema change safety | categorise + recreate | **schema evolution** with compatibility rules |

So the design principle is:

> **Don't re-implement versioning in the framework. Use Iceberg branches, tags
> and snapshots directly, and keep the framework thin: a DAG, fingerprints, a
> WAP orchestrator, and pluggable engines.**

This is the difference between "dbt/SQLMesh pointed at Iceberg" and a system
designed *for* Iceberg.

## 4. Architecture

```
        ┌───────────────────────── cleyrop-dm ─────────────────────────┐
 models │  parse & config → DAG (SQLGlot) → fingerprints → plan         │
  .sql  │        │                                    │                 │
  .py   │        ▼                                    ▼                 │
        │   ┌─────────┐   compute    ┌──────────────────────────────┐   │
        │   │ engines │◀────────────▶│  runner  (apply under WAP)   │   │
        │   │ duckdb  │   Arrow      └──────────────┬───────────────┘   │
        │   │ spark   │                             │ pyiceberg          │
        │   │ connect │                             ▼                    │
        │   └─────────┘        ┌───────────────────────────────────┐    │
        │                      │        Iceberg catalog            │    │
   state│  fingerprints +      │  analytics.customer_orders        │    │
   .db  │  snapshot history    │    main(prod) · env_dev · wap     │    │
        │                      │    snapshots → time travel        │    │
        └──────────────────────┴───────────────────────────────────┘    │
```

Components (all in `cleyrop_dm/`):

- **`config`** — project (`cleyrop_project.yml`) and per-model config.
- **`model`** — `SqlModel` / `PythonModel`; parses the `-- @key:` header DSL and
  infers SQL dependencies with SQLGlot.
- **`dag`** — resolves refs to models vs declared sources; topological order;
  cycle detection.
- **`fingerprint`** — recursive content hash per model → change detection.
- **`engines`** — `DuckDBEngine`, `SparkConnectEngine`, over a tiny `Engine`
  interface (run SQL over named Arrow relations → Arrow).
- **`catalog`** — the Iceberg layer: environments-as-branches, WAP, promotion,
  time travel.
- **`audits`** — dbt-style tests, evaluated on staged data before publish.
- **`state`** — applied fingerprints + snapshot history (SQLite here; catalog-
  adjacent in production).
- **`plan` / `runner`** — decide what will change, then apply it safely.
- **`cli`** — `plan` · `apply` · `run` · `promote` · `history` · `ls`.

## 5. Models: SQL and Python, no Jinja

A model is a named dataset that yields an Arrow table.

**SQL models** are a `SELECT` with a comment header — SQLMesh-style, so the SQL
stays valid and runnable on its own:

```sql
-- @model: customer_orders
-- @materialization: table
-- @audits: not_null(customer_id), unique(customer_id), row_count_at_least(1)
SELECT c.customer_id, c.name, count(o.order_id) AS n_orders, ...
FROM stg_customers c LEFT JOIN stg_orders o USING (customer_id)
GROUP BY 1, 2
```

Dependencies (`stg_customers`, `stg_orders`) are **parsed out of the SQL** with
SQLGlot — CTE names excluded, sources vs models classified by the DAG. No
`ref()` macros, no Jinja rendering step, no string soup.

**Python models** are for what SQL is bad at (feature engineering, scoring):

```python
META = {"name": "customer_features", "depends_on": ["customer_orders"], ...}
def model(ctx):
    co = ctx.ref("customer_orders")   # Arrow, read from the current environment
    return pa.table({...})            # return a pyarrow.Table
```

Both flavours get the same DAG, fingerprints, WAP, audits and time travel. The
runner reads a model's upstreams from the *current environment's Iceberg branch*
and hands them to the engine (or to the Python `ctx`).

## 6. The DAG and fingerprints

Every model gets a **fingerprint**: a hash of its own logic + config, combined
with the fingerprints of everything it depends on. Two consequences:

- **Recursive dirtiness for free** — change one model and every descendant's
  fingerprint changes, so they're rebuilt without special-casing.
- **`plan` before `apply`** — diff desired fingerprints against the last-applied
  ones (from the state store) and show exactly which models will move, per
  environment, *before any data changes*. This is what makes changes reviewable.

Unchanged models are skipped: their Iceberg data is still valid, so there's
nothing to do. (SQLMesh's core insight; dbt lacks it.)

## 7. Environments = Iceberg branches (the core move)

Each managed table lives once, in the project namespace (e.g.
`analytics.daily_revenue`). Environments are **branches** of that table:

- `prod`  → the `main` branch.
- `dev` / any feature env → a branch `env_<name>`, created off `main`.

Creating a dev environment is **zero-copy and instant** — a branch is just a
named pointer to a snapshot; no data is duplicated. Building a model in `dev`
writes only to `env_dev`; readers on `prod`/`main` see nothing change. When a
dev model reads an upstream that *wasn't* rebuilt in dev, the scan simply falls
back to `main` — dev transparently reuses prod data (exactly SQLMesh's virtual-
environment reuse, but at the storage layer).

The demo shows this precisely: after an incremental run in `dev`, the table
carries both refs and the two environments show different data:

```
Iceberg refs on daily_revenue: ['env_dev', 'main']
dev  daily_revenue:  {...'2026-06-05': 225.0}   # 5 days
prod daily_revenue:  {...}                       # 4 days — untouched
```

## 8. Write-Audit-Publish (WAP)

Every materialisation is transactional at the table level, but we want the
publish to be gated by **data audits**, not just by a successful write. Iceberg
branches give us the classic WAP pattern natively:

```
 1. WRITE    branch `wap` off the environment head; write the new data to `wap`
 2. AUDIT    scan `wap`; run the model's audits on exactly what would be published
 3. PUBLISH  audits pass → fast-forward the env branch to `wap`, drop `wap`
             audits fail → drop `wap`; the environment never moved
```

Mapped to PyIceberg primitives (see `catalog.py`):

| Step | PyIceberg call |
|---|---|
| branch | `table.manage_snapshots().create_branch(head, "wap")` |
| write (full) | `table.overwrite(arrow, branch="wap")` |
| write (incremental) | `table.upsert(arrow, join_cols=key, branch="wap")` |
| audit | `table.scan(snapshot_id=wap_head).to_arrow()` → `run_audits(...)` |
| publish (main) | `manage_snapshots().set_current_snapshot(wap_head)` |
| publish (env branch) | move the branch ref to `wap_head` |
| abort | `manage_snapshots().remove_branch("wap")` |

The demo's audit-veto act proves the guarantee: a `-500` refund makes a day's
revenue negative, the `expression(revenue >= 0)` audit fails on the `wap`
branch, the publish is vetoed, **prod is byte-for-byte unchanged**, and the
staging branch is cleaned up. Bad data never becomes visible.

## 9. Materializations → Iceberg operations

| Materialization | Meaning | Iceberg operation |
|---|---|---|
| `table` | full refresh | `overwrite` (atomic replace) on the WAP branch |
| `incremental` | merge new/changed rows by `unique_key` | `upsert(join_cols=…)` (row-level MERGE) |
| `view` | ephemeral staging, never persisted | inlined/recomputed on demand; recorded for lineage only |

Incremental models run on a cadence to pick up new source rows even when their
code is unchanged (`--force` / `force=True`), just like a scheduled `dbt run` or
a SQLMesh interval. Fingerprints govern *code* changes; the schedule governs
*data* arrival.

## 10. Engines: one catalog, many compute layers

The `Engine` contract is deliberately tiny: *run SQL over named Arrow relations,
return Arrow*. Everything else (WAP, audits, state) is engine-independent.

- **DuckDB** — in-process; upstream Iceberg data is handed over as Arrow
  (zero-copy) and the model SQL runs locally. Perfect for dev, CI and
  small/medium datasets. This is what the demo and tests run on.
- **Spark Connect** — a thin gRPC client submits the same SQL to a remote Spark
  cluster (no local JVM). For large datasets, `run_sql_on_catalog(...)` lets
  Spark read the Iceberg tables **directly from the shared catalog** and never
  ship data through the client — the scalable path.
- **PyIceberg** — the metadata/commit layer used everywhere internally (branches,
  snapshots, upsert), plus Arrow compute for Python models.

Because all engines read and write the same catalog, DuckDB locally and Spark in
production are interchangeable for the *same* model definitions.

## 11. Governance, contracts and sovereignty

For a sovereign platform, *how* data changes matters as much as *what* it
contains:

- **Data never leaves the lake.** All materialisation is catalog-native; compute
  reads and writes the customer's own Iceberg storage. Spark's catalog push-down
  keeps even large joins inside the cluster.
- **Audits are blocking and pre-publication.** Quality is enforced *before*
  anything is visible, not detected afterwards.
- **Everything is attributable and reversible.** The state store records which
  fingerprint and which snapshot is live in each environment; Iceberg keeps the
  full snapshot history. Any prior state is one `snapshot_id` away (§ time
  travel), and rollback is a ref move.
- **Schema is a contract.** Iceberg's schema-evolution rules (safe adds/renames
  via field IDs; blocked incompatible changes) back a model's declared output
  contract. Breaking schema changes surface in `plan`.
- **Lineage** falls out of the DAG (model↔model, model↔source) and can be
  emitted to a catalog / OpenLineage for the data-governance layer.

## 12. Lifecycle

```
edit model → plan (what will change, per env)
           → apply to dev   (WAP + audits on env_dev, prod untouched)
           → inspect dev data / lineage
           → promote dev → prod   (blue/green: fast-forward main, atomic)
           → (later) time-travel / rollback if needed
```

`promote` is a ref fast-forward per table — instant and atomic, the storage-
layer equivalent of SQLMesh's view swap, with no recompute.

## 13. Why not just use dbt or SQLMesh directly?

You can, and for a pure-warehouse shop you probably should. This design exists
because Cleyrop is **Iceberg-first, multi-engine and sovereign**:

- dbt would give us Jinja, full-copy environments and post-hoc tests — a poor
  fit for zero-copy branches and pre-publish gating.
- SQLMesh is much closer in spirit (fingerprints, virtual envs, audits, plan/
  apply) and is the primary inspiration — but its virtual layer re-implements in
  views what Iceberg does in branches, and it isn't designed around Spark
  Connect + PyIceberg + DuckDB over one catalog.

`cleyrop-dm` keeps SQLMesh's *concepts* and rebuilds the *mechanism* on Iceberg
primitives, which is simpler, atomic, and free of a shadow versioning system.

## 14. Production hardening (roadmap)

The prototype is intentionally small. To run this for real:

1. **Catalog** — swap the local SQLite catalog for **REST / Nessie / Polaris /
   Glue**; only `cleyrop_project.yml` changes. Nessie/Polaris add *catalog-level*
   branching across many tables (multi-table atomic promotion).
2. **Concurrency** — rely on Iceberg optimistic commits; add retry/backoff on
   commit conflicts and per-model locks in the state store.
3. **Orchestration** — schedule `plan`/`apply` from Airflow/Dagster; incremental
   models run on their cadence.
4. **Column-level lineage** — SQLGlot can derive it from the parsed SQL; emit to
   the governance catalog.
5. **Maintenance** — schedule Iceberg compaction, snapshot expiration and orphan-
   file cleanup (retaining enough history for the rollback SLA).
6. **Streaming/CDC** — land raw via Kafka/Flink into Iceberg; incremental models
   pick it up by time window.
7. **RBAC & audit log** — enforce who can `promote` to `prod`; sign every apply
   with actor + fingerprint + snapshot for the sovereign audit trail.
8. **Backfills & data tests as gates in CI** — run `plan` + audits on a dev
   branch in CI on every PR; block merge on audit failure.

## 15. Concept map

| Concept | dbt-core | SQLMesh | **cleyrop-dm (Iceberg-native)** |
|---|---|---|---|
| Model | `.sql` + Jinja | `.sql`/`.py`, SQLGlot | `.sql`/`.py`, SQLGlot, header DSL |
| Dependencies | `ref()`/`source()` | inferred | inferred (SQL) + explicit (Python) |
| Change detection | — | fingerprints | recursive fingerprints |
| Environment | target schema (copy) | virtual layer (views) | **Iceberg branch (zero-copy)** |
| Safe publish | manual blue/green | view swap | **WAP branch + fast-forward** |
| Tests | post-hoc `tests/` | blocking audits | **pre-publish audits (on `wap`)** |
| Incremental | `is_incremental()` | by time range | `upsert(join_cols)` (Iceberg MERGE) |
| Rollback / history | — | state | **Iceberg snapshots / `rollback`** |
| Promote | rebuild in prod | promote virtual env | **fast-forward `main` ref** |

---

**In one line:** keep SQLMesh's ideas, drop its shadow versioning, and let
Iceberg's branches, snapshots and schema evolution *be* the version-control layer
for Cleyrop's data — driven by SQL and Python models over DuckDB and Spark
Connect on a single sovereign catalog.
