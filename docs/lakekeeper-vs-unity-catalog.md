# Lakekeeper vs. Unity Catalog OSS — Deep-Dive Comparison

> Source-level comparison of two open-source lakehouse catalogs, analyzed from
> freshly cloned repositories on **2026-07-02**:
>
> - **Lakekeeper** `f6b7a2d` — v0.13.1 (github.com/lakekeeper/lakekeeper)
> - **Unity Catalog OSS** `25a5669` — v0.5.0-SNAPSHOT (github.com/unitycatalog/unitycatalog)
>
> All claims were verified against build files, OpenAPI specs, server code,
> authorization models, CI workflows, docs, and roadmaps — not marketing pages.

---

## The verdict in three sentences

These projects overlap far less than their marketing suggests: they answer
different questions.

**Lakekeeper** asks *"what is the best possible Iceberg REST catalog?"* — and
delivers a production-hardened, single-binary answer with near-complete spec
coverage, downscoped credential vending on four storage backends, OpenFGA
fine-grained authorization, change events, and a serious operations story.

**Unity Catalog OSS** asks *"what should an open catalog for data **and** AI
look like?"* — and delivers the widest asset model in open source (tables,
volumes, functions, ML models, GenAI tool integrations) on a codebase that is
still visibly early: LF *sandbox* maturity, H2 file database by default, auth
off by default, and an Iceberg endpoint that is read-only today.

---

## 1. At a glance

| | Lakekeeper | Unity Catalog OSS |
|---|---|---|
| **Version analyzed** | 0.13.1 (released 2026-06-30) | 0.5.0-SNAPSHOT (main, 2026-07-02) |
| **License** | Apache-2.0 | Apache-2.0 |
| **Governance** | Vendor-backed (Vakamo Inc.); open core + commercial "Lakekeeper Plus" | Databricks-originated; LF AI & Data Foundation **sandbox** project |
| **Language / stack** | Rust 2024 · axum 0.8 · tokio · sqlx | Java 17 (sbt) · Armeria 1.28 · Hibernate 6.5 · React UI · Python AI libs |
| **Code size (approx.)** | ~175k LOC Rust | ~60k LOC Java (+ UI, Python) |
| **Metadata store** | PostgreSQL ≥15 only; encrypted secrets; transactional migrations | H2 file DB by default; MySQL/Postgres examples; Hibernate `hbm2ddl.auto=update`, no migration tooling |
| **Core protocol** | Apache Iceberg REST Catalog + Management API + Generic Tables API | Own UC REST API + Delta managed-commits API + read-only Iceberg REST subset |
| **Asset types** | Iceberg tables & views, generic tables, warehouses, projects, users, roles | Catalogs, schemas, tables, **volumes**, **functions/UDFs**, **ML models**, external locations, storage credentials |
| **Authorization** | OpenFGA (OSS), Cedar (Plus), custom trait; OPA bridge for Trino | jCasbin grants with SQL-style privileges |
| **AI features** | None (by design) | `unitycatalog-ai` + 9 GenAI framework adapters, MLflow registry |
| **Production posture** | Stateless/HA, Prometheus, health probes, migration discipline | Helm chart `0.0.1-pre.1`; monitoring/auditing/DB-upgrades are open roadmap items; "APIs… should not be assumed stable" |

---

## 2. Philosophy: a scalpel vs. a swiss-army knife

**Lakekeeper is deliberately narrow and deep.** It implements one standard —
the Apache Iceberg REST Catalog specification — and treats everything else
(multi-project tenancy, fine-grained permissions, change events, credential
vending, soft-deletes) as hardening around that single job. It is explicitly
*not* an identity provider, query engine, or governance suite; engines connect
through the open Iceberg protocol.

**Unity Catalog OSS is deliberately broad.** Its three-level namespace
(`catalog.schema.asset`) governs not just tables but volumes (arbitrary
files), functions (SQL/Python UDFs), and registered ML models with versioning
— plus a Python ecosystem (`unitycatalog-ai`) that turns catalog functions
into tools for GenAI agents. The trade-off: each capability is shallower and
younger than Lakekeeper's equivalent, and several headline Unity Catalog
features (lineage, auditing, Delta Sharing, federation, ABAC) exist only in
Databricks' commercial platform, not in the OSS repo.

> **Takeaway** — If your unit of governance is "an Iceberg table," Lakekeeper
> covers it with more depth today. If your unit of governance is "data *and*
> AI assets," Unity Catalog is the only one of the two that even models the
> problem.

---

## 3. Architecture

### Lakekeeper — a Rust workspace built around traits

- **Single static binary** (`lakekeeper`) with subcommands for `migrate`,
  `serve`, `healthcheck`, and OpenFGA model reconciliation. No JVM or Python
  runtime. The web UI (separate "Console" project, pinned v0.19.0) compiles in
  behind a feature flag.
- **~175k lines of Rust** across 10+ workspace crates: core catalog
  (`crates/lakekeeper`), Postgres backend (`lakekeeper-storage-postgres`, 65
  sqlx migrations), storage I/O (`crates/io`: S3/ADLS/GCS), OpenFGA authorizer,
  Kafka and NATS CloudEvents publishers, Vault KV2 secrets, iceberg-rust
  extensions.
- **Extensible by generics:** the server is
  `serve<CatalogStore, SecretStore, Authorizer, Authenticator>`, with
  documented traits for authorization, change events, secret stores, contract
  verification, and admission gates.
- **Stateless by design:** all state lives in Postgres (read/write pool split
  supported); horizontal scaling is trivial.

### Unity Catalog — a Java monorepo with many surfaces

- **Armeria HTTP server** mounting services at `/api/2.1/unity-catalog/` plus
  a control plane at `/api/1.0/unity-control/` (SCIM2 users + OAuth token
  exchange). 142 main server classes.
- **Three OpenAPI specs** drive code generation: `api/all.yaml` (catalog API),
  `api/control.yaml` (users/auth), and `api/delta.yaml` — a Delta-centric
  commit API "inspired by the Iceberg REST style."
- **Hibernate ORM persistence** with 17 DAO entities; H2 file DB out of the
  box, MySQL/Postgres via compose examples; schema evolution via Hibernate
  auto-DDL (no versioned migration system yet).
- **Monorepo beyond the server:** Java + Python SDKs (OpenAPI-generated), a
  `bin/uc` CLI built on Delta Kernel, Spark and Hadoop connectors, a React 18
  + Ant Design UI, a Helm chart, and the `ai/` Python monorepo.

---

## 4. Table formats: Iceberg, Delta, and the interop gap

The sharpest technical divide.

**Lakekeeper is Iceberg-native.** A unit test asserts every path in the
vendored Apache Iceberg REST spec is implemented **except** the OAuth token
endpoint and server-side scan planning. Coverage includes nested namespaces,
views, registration, rename, metrics, multi-table `/transactions/commit`, and
`loadCredentials`, plus per-warehouse Iceberg format-version policies.
Non-Iceberg formats (Lance, Delta, CSV, Parquet) get the **Generic Tables
API** — credential vending, soft-delete/undrop, 16 per-action permissions —
but no commit coordination or schema enforcement.

**Unity Catalog is Delta-native.** Delta Lake is first-class through Delta
Kernel, and the marquee 0.4→0.5 feature is **catalog-managed commits** — a
formal Managed Tables protocol (spec v1.0, 2026-06-11) where the catalog
coordinates Delta writes. Its **Iceberg REST endpoint is read-only today**
(`GET /config`, namespaces, table loads, metrics — no create, no commit).
Full Iceberg create/read/write and UniForm are v0.5+ roadmap items.

| Capability | Lakekeeper | Unity Catalog OSS |
|---|---|---|
| Iceberg REST: read | ✅ Full | 🟡 Read-only subset |
| Iceberg REST: write/commit | ✅ Incl. multi-table transactions | ❌ Roadmap (v0.5+) |
| Iceberg views | ✅ With DEFINER/INVOKER security | 🟡 GET endpoints only |
| Delta managed tables + coordinated commits | ❌ Delta only as uncoordinated generic table | ✅ Managed Tables protocol v1.0 |
| Other formats (Lance, Parquet, CSV…) | ✅ Generic Tables API | 🟡 External tables; Hudi via UniForm claim |
| Server-side scan planning | ❌ Explicitly unimplemented | ❌ Not present |
| Volumes / files / UDFs / ML models | ❌ | ✅ All first-class asset types |

---

## 5. Storage & credential vending

Both vend short-lived, downscoped cloud credentials so engines never hold
long-lived keys. Depth differs:

| | Lakekeeper | Unity Catalog OSS |
|---|---|---|
| **Backends** | S3 + S3-compatible (MinIO, R2, Ceph…), ADLS Gen2, **OneLake/Fabric** (0.13), GCS | S3, ADLS, GCS, local FS |
| **AWS mechanism** | STS AssumeRole downscoped to table location, external IDs, session tags, **SSE-KMS vending**; plus **remote request signing** mode | Master-role STS with downscoped session policies; legacy per-bucket static config |
| **Azure / GCP** | Downscoped SAS tokens (ADLS/OneLake); downscoped STS (GCS); system/managed identities | SAS-style ADLS credentials; GCP token generator |
| **Scoping** | Per-table location; overlapping-location prevention per warehouse; `X-Iceberg-Access-Delegation` negotiation | Per-asset, per-operation temp credentials for tables, volumes, model versions, paths |
| **Client plumbing** | Standard Iceberg REST vending — any compliant engine | Custom Hadoop connector with vended-token providers (S3/ABFS/GCS) |

Lakekeeper's remote-signing mode and SSE-KMS support have no OSS UC
equivalent. UC's per-asset-type vending (volumes, model artifacts) reflects
its broader asset model.

---

## 6. Authentication & authorization

### Authentication

- **Lakekeeper**: JWT validation against any OIDC provider (multiple
  providers since 0.13) plus native **Kubernetes service-account** auth.
  Explicitly not an IdP — no local users, no stored secrets. Pluggable
  post-auth admission gates.
- **Unity Catalog**: auth **disabled by default**. When enabled: OAuth 2.0
  token exchange — validates an external IdP token (Google, Entra ID, Okta
  documented) then mints its own RSA-signed JWT. Maintains a local user DB
  with SCIM2 management and an auto-created admin token.

### Authorization — the widest gap in the comparison

| | Lakekeeper | Unity Catalog OSS |
|---|---|---|
| Engine | OpenFGA relationship-based FGA (model versioned v2.1→v4.7 with migrations); Cedar in Plus; custom trait | jCasbin, RBAC-ish model, hierarchical resources |
| Granularity | Server → project → warehouse → namespace → table/view/generic-table; grant-management meta-permissions; nested roles; role assumption | SQL-style privileges (USE CATALOG, SELECT, MODIFY, EXECUTE, READ VOLUME, CREATE MODEL…) per securable; OWNER handling |
| Engine-side enforcement | OPA bridge: shared Trino clusters enforce Lakekeeper permissions per end user | None; SQL DCL via Spark is roadmap |
| Audit | Authz audit events with privilege source + contributing policies (0.13) | Not implemented; roadmap v0.5+ |
| Row filters / column masks / ABAC | ❌ Not modeled | ❌ Open "❓" roadmap questions |

> **Takeaway** — Neither does row/column-level security in open source. Above
> table level, Lakekeeper's authorization is materially more mature; UC's own
> roadmap targets "permission parity with Databricks UC" as future work.

---

## 7. AI & ML: where Unity Catalog stands alone

Lakekeeper has no AI/ML surface, deliberately. Unity Catalog dedicates a whole
Python monorepo to it:

- **`unitycatalog-ai`**: create, retrieve, and *execute* catalog-registered
  functions as GenAI agent tools — with clients for both the OSS server and
  Databricks-managed UC. Execution happens locally in the caller's process
  (README carries sandboxing warnings).
- **Nine framework adapters**, each a PyPI package: LangChain, OpenAI,
  Anthropic, CrewAI, LlamaIndex, AutoGen, LiteLLM, Gemini, DSPy. (No MCP
  server anywhere in the repo.)
- **ML model registry**: registered models + versions as catalog assets,
  temporary credential vending for model artifacts, MLflow integration tested
  in CI.

---

## 8. Operations

| | Lakekeeper | Unity Catalog OSS |
|---|---|---|
| Packaging | Static binary, Docker (quay.io), Helm on Artifact Hub, K8s operator in dev | Docker + compose (server + UI), tarball, Helm `0.0.1-pre.1` |
| Scaling / HA | Stateless, horizontally scalable; documented HA checklist | Single-node oriented; multi-tenancy is roadmap |
| Schema upgrades | Transactional versioned migrations; refuses to start on unmigrated/downgraded DB | Hibernate auto-DDL; "DB schema upgrades" an open roadmap question |
| Observability | Prometheus (HTTP, Tokio, PG pools), health endpoints, endpoint-statistics API | Log4j2 request logging; monitoring "❓" on roadmap |
| Change events | CloudEvents to Kafka or NATS; contract-verification veto hooks | Not implemented |
| Data safety | Soft-delete + undrop, deletion protection, anti-purge storage option | Standard deletes |
| Table maintenance | Snapshot expiry & orphan cleanup — **Plus (paid) only** | Not offered |

Caveat cutting the other way: several Lakekeeper governance extras (Cedar,
admission enforce gate, automated maintenance, UI branding) are commercial
Plus features. UC OSS has no paid tier in-repo; its gap is instead with the
Databricks-hosted product.

---

## 9. Ecosystem & CI honesty

**Lakekeeper** speaks a standard, and its CI proves the integrations: the
matrix runs Spark (Iceberg 1.8/1.9/1.10), Trino (incl. Trino+OPA), StarRocks,
PyIceberg, and DuckDB against OpenFGA, Vault, ADLS, and S3
remote-signing/STS/KMS variants. Examples compose in Keycloak + OpenFGA.

**Unity Catalog** documents a broad list — Spark (own connector, cross-built),
DuckDB, Trino, Daft, Kuzu, PuppyGraph, SpiceAI, StarRocks/CelerData, Apache
XTable — plus Java/Python SDKs and the Delta-Kernel CLI. But a striking number
of CI workflows are checked in **disabled** (docker-build, release, tarball,
tutorial, MLflow integration, UI docker build), and cloud integration tests
require manually configured resources.

---

## 10. Roadmaps

**Lakekeeper** (CHANGELOG & docs): more catalog backends (SQLite,
FoundationDB named); Kubernetes operator; cascade-drop API; external tables;
deeper non-Iceberg support via Generic Tables; scale hardening for "large
fleets."

**Unity Catalog** (`roadmap.md`):
- **0.5 priorities:** managed Delta tables (coordinated commits stable),
  experimental Metric Views, modular authentication.
- **v0.5+:** multi-tenancy, groups & service principals, expanded privileges
  toward "permission parity with Databricks UC," auditing, UniForm
  read-as-Iceberg, full Iceberg CRW, views, streaming tables, managed volumes.
- **Open questions (may never land in OSS):** RBAC, row filters/column masks,
  ABAC, lineage, Delta Sharing, federation, monitoring, change events.

---

## 11. Decision guide

| Scenario | Pick |
|---|---|
| Iceberg-first lakehouse, self-hosted, multiple engines | **Lakekeeper** — full spec coverage, four-cloud vending, FGA, HA, CI-proven engines |
| Delta Lake estate, or governing files + UDFs + ML models | **Unity Catalog** — only UC models volumes/functions/models and coordinates Delta commits |
| GenAI agents calling governed tools | **Unity Catalog** — `unitycatalog-ai` + nine adapters is unique |
| Strict security & compliance now | **Lakekeeper** — OIDC + K8s auth, versioned FGA, audit events, encrypted secrets/Vault. UC ships auth-off with no audit log |
| Betting on ecosystem gravity | **Depends** — UC has the brand + LF umbrella but sandbox maturity; Lakekeeper has a smaller vendor but a faster, more disciplined release train |
| Both worlds (Delta + Iceberg, tables + AI) | **Run both / revisit** — they coexist; watch UC's UniForm and Iceberg-write items |

---

## Appendix A — Lakekeeper deep-dive notes

- Workspace crates: `lakekeeper` (core), `lakekeeper-bin`,
  `lakekeeper-storage-postgres`, `io`, `iceberg-ext`, `authz-openfga`,
  `events-kafka`, `events-nats`, `secrets-kv2`, `integration-tests`.
- Three HTTP APIs: Iceberg REST (`/catalog/v1`), Management
  (`/management/v1`), Data/Generic Tables (`/lakekeeper/v1`).
- Unimplemented Iceberg REST endpoints: `/v1/oauth/tokens`, scan planning
  (`/plan`, `/plan/{id}`, `/tasks`).
- Entity hierarchy: Server → Projects → Warehouses → nested Namespaces →
  Tables/Views/Generic Tables; nested roles with bounded depth.
- Notable extras: case-insensitive/case-preserving identifiers (PG ICU
  collation), fuzzy search, task queues, endpoint statistics, DEFINER/INVOKER
  view security, 403-not-404 anti-enumeration, `x-assume-role` header.
- Limitations: Postgres-only; opaque tokens unsupported; no native TLS
  termination; all tables assumed managed; encrypted Iceberg tables skipped by
  maintenance jobs; several governance extras Plus-only.

## Appendix B — Unity Catalog deep-dive notes

- sbt modules: `server`, `serverModels`/`controlModels`, `client` (Java),
  `pythonClient`, `cli`, `spark` + `hadoop` connectors, `integrationTests`;
  outside sbt: `ui/`, `ai/`, `helm/`, `docs/`.
- DAO entities: Catalog, Schema, Table, Column, Volume, Function,
  RegisteredModel, ModelVersion, Credential, ExternalLocation, Metastore,
  User, Property, StagingTable, DeltaCommit, Dependency, FunctionParameter.
- Iceberg REST endpoint mounted at `/api/2.1/unity-catalog/iceberg/v1/…`;
  read-oriented only (config, namespaces, table GET/HEAD, views GET, metrics).
- Temporary credential services per asset type: tables, volumes, model
  versions, paths.
- Auth: OAuth token exchange (`urn:ietf:params:oauth:grant-type:token-exchange`)
  at `/api/1.0/unity-control/auth/tokens`; auto-generated 2048-bit RSA
  keypair; SCIM2 user management; admin token auto-created.
- Not in OSS (Databricks-commercial only or open questions): lineage,
  auditing, Delta Sharing, federation, row filters, column masks, ABAC,
  system tables, search.

---

*Generated 2026-07-02 from source analysis of both repositories. Both projects
move quickly — re-verify before committing to either.*
