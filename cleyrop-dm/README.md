# cleyrop-dm — Cleyrop Dataset Management

A small, opinionated framework for managing **Cleyrop datasets** (Apache Iceberg
tables) with **Python and SQL transformations**.

It takes the best ideas from [dbt-core](https://github.com/dbt-labs/dbt-core)
and [SQLMesh](https://github.com/TobikoData/sqlmesh) and makes them **native to
Iceberg** — using Iceberg branches, tags and snapshots to get virtual
environments, Write-Audit-Publish and time travel *for free*, instead of
re-implementing those semantics in the framework.

See **[DESIGN.md](DESIGN.md)** for the full "why" and the architecture.

---

## The idea in one picture

```
 models/                         engines                   Iceberg lakehouse
 ├─ stg_orders.sql   ─┐      ┌─ DuckDB (local/CI) ─┐      ┌─ analytics.customer_orders
 ├─ customer_orders  ─┼─DAG─→┤  Spark Connect (⤢)  ├─WAP─→┤    main   = prod  (branch)
 ├─ daily_revenue    ─┤      └─ PyIceberg (Arrow)  ┘      │    env_dev        (branch)
 └─ customer_features ┘         one catalog, many engines  └─ snapshots = time travel
       (.sql or .py)
```

* **Models** are datasets. Each is a `.sql` file (a `SELECT` + a `-- @key:` header)
  or a `.py` file (`META` + `model(ctx)` returning Arrow). SQL dependencies are
  inferred with SQLGlot — no Jinja, no `ref()` macros.
* **Environments are Iceberg branches.** `prod` is `main`; `dev` (or any feature
  env) is a zero-copy branch. Building in `dev` never touches `prod`.
* **Write-Audit-Publish.** Every build writes to a short-lived `wap` branch, runs
  its audits there, and only fast-forwards the environment branch if they pass.
  Bad data is never visible.
* **Time travel & rollback** are just Iceberg snapshot scans.
* **Fingerprints** (à la SQLMesh) skip rebuilds of unchanged models and let
  `plan` show exactly what a change will do before any data moves.

## Quickstart

```bash
pip install -e .            # or: pip install "pyiceberg[sql-sqlite,pyarrow]" duckdb sqlglot pyyaml

python demo.py             # fully self-contained end-to-end walkthrough
pytest -q                  # unit + end-to-end tests (local Iceberg warehouse)

# CLI (against a project with a configured catalog):
cleyrop-dm --project examples/retail ls
cleyrop-dm --project examples/retail plan    --env dev
cleyrop-dm --project examples/retail apply   --env dev
cleyrop-dm --project examples/retail promote --from dev --to prod
cleyrop-dm --project examples/retail history --model daily_revenue
```

`demo.py` walks the whole lifecycle: first production load → zero-copy dev branch
with an incremental run (prod untouched) → blue/green promotion → an audit that
vetoes a bad publish → time travel.

## A model

```sql
-- @model: daily_revenue
-- @materialization: incremental
-- @unique_key: order_date
-- @audits: not_null(order_date), unique(order_date), expression(revenue >= 0)

SELECT order_date, count(*) AS n_paid_orders, sum(amount) AS revenue
FROM stg_orders
WHERE status = 'paid'
GROUP BY order_date
```

```python
# customer_features.py  — Python when SQL is awkward
META = {"name": "customer_features", "depends_on": ["customer_orders"],
        "audits": ["not_null(customer_id)", "unique(customer_id)"]}

def model(ctx):
    co = ctx.ref("customer_orders")     # Arrow table, read from the current env
    ...                                  # return a pyarrow.Table
```

## Layout

```
cleyrop_dm/
  config.py      project + model config           catalog.py   Iceberg WAP / branches / time travel
  model.py       SQL & Python models, header DSL  audits.py    data audits (dbt-style tests)
  dag.py         ref/source graph via SQLGlot      state.py     applied fingerprints + history
  fingerprint.py content hashes & change detection plan.py      what a change will do
  engines/       duckdb · spark_connect · base     runner.py    compute + apply under WAP
  cli.py         the `cleyrop-dm` command
examples/retail/ a runnable sample project
demo.py          end-to-end walkthrough           tests/       unit + e2e
```

## Engines

| Engine | Use | Runs data through client? |
|--------|-----|---------------------------|
| **DuckDB** | local dev, CI, small/medium data | yes (Arrow, zero-copy) |
| **Spark Connect** | production scale, distributed | no — reads Iceberg directly from the catalog (`run_sql_on_catalog`) |
| **PyIceberg** | metadata ops, WAP, Arrow compute | — (used internally) |

The same model SQL runs unchanged across engines; only *where* the compute
happens differs.
