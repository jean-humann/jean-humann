# Lakekeeper fork: Unity Catalog-compatible multimodal objects

A fork of [lakekeeper/lakekeeper](https://github.com/lakekeeper/lakekeeper)
(base: upstream `main` @ `f6b7a2df`, v0.13.1 line) extending Lakekeeper with a
**Unity Catalog-compatible REST API** covering all Unity Catalog OSS object
types — **volumes, functions/UDFs, registered models + model versions** — with
temporary-credential vending and OpenFGA fine-grained authorization, e2e-tested
against the unmodified Unity Catalog client ecosystem.

**Branch:** `multimodal-uc-objects` — 7 commits, 117 files changed,
+23,512 / −121 lines.

## What it does

Mounts `/api/2.1/unity-catalog/` next to Lakekeeper's Iceberg REST, Management
and Data APIs (config flag `LAKEKEEPER__ENABLE_UC_COMPAT_API`, default on):

| UC resource | Backing | Highlights |
|---|---|---|
| Catalogs | Lakekeeper warehouses (read-mapped) | list/get; create via management API by design |
| Schemas | top-level namespaces | full CRUD, delegates to upstream namespace handlers (same authz/idempotency) |
| Volumes | new `uc_volume` entity | MANAGED + EXTERNAL, location-overlap checks vs tables/models, comment updates |
| Functions | new `uc_function` entity | `function_info` stored verbatim (JSONB) → byte-fidelity round-trip for `unitycatalog-ai` client-side execution |
| Registered models + versions | new `uc_model`/`uc_model_version` | serialized integer version assignment, `PENDING_REGISTRATION → READY` finalize lifecycle |
| Temporary credentials | Lakekeeper storage profiles | `READ_/WRITE_VOLUME`, `READ_/READ_WRITE_MODEL_VERSION`; aws/azure/gcp blocks + epoch-ms expiry; READ_WRITE only while a version is pending |

Authorization: new `CatalogVolumeAction`/`CatalogFunctionAction`/
`CatalogModelAction` enums wired through the `Authorizer` trait; **OpenFGA
model v4.8** adds `lakekeeper_volume`, `lakekeeper_function` (with `execute`),
`lakekeeper_model` types plus assignments/authorizer-actions permission
endpoints; data-plane actions stay excluded from instance-admin bypass;
404 existence-masking pre-grant. Docs: `docs/docs/uc-compat.md` in the fork.

## Verification (all green at delivery)

- **Rust**: 15 `#[sqlx::test]` postgres tests, 33 UC integration tests,
  95+ lib tests, plus upstream suites unbroken (`cargo check --all-features`
  clean; 34/34 namespace tests after the drop-guard fix).
- **Live e2e, `MODE=allowall`** (real server + Postgres + OpenFGA + MinIO):
  **40 passed** — unmodified `unitycatalog-client` 0.4.1 CRUD for every type;
  `unitycatalog-ai` 0.4.0 create/retrieve/**execute** of a Python UDF;
  LangChain + OpenAI toolkits generating and invoking tools; DuckDB reading
  volume parquet through vended STS creds; boto3 model-artifact upload/download
  with pending-only write creds; MinIO session-policy downscoping verified.
- **Live e2e, `MODE=openfga`** (offline OIDC stub minting real JWTs):
  **18 passed** — anonymous → 401; bootstrap-as-admin; owner action sets;
  second user 404-masked pre-grant; grant via assignments API; then 200 read /
  403 `PERMISSION_DENIED` write with a select-only grant; function/model
  spot checks.

## Publishing this as a real GitHub fork

This session couldn't create a GitHub fork (repo-scoped credentials), so the
branch ships as a bundle + patch series:

```bash
# 1. Fork lakekeeper/lakekeeper on GitHub (one click), then:
git clone https://github.com/<you>/lakekeeper.git && cd lakekeeper
git fetch origin f6b7a2df || git fetch https://github.com/lakekeeper/lakekeeper.git main

# 2a. From the bundle (exact commits, preferred):
git bundle verify ../multimodal-uc-objects.bundle
git fetch ../multimodal-uc-objects.bundle multimodal-uc-objects:multimodal-uc-objects

# 2b. ...or from the patch series:
git checkout -b multimodal-uc-objects f6b7a2df && git am ../patches/*.patch

# 3. Push
git push -u origin multimodal-uc-objects
```

Build note: `utoipa-swagger-ui` downloads Swagger UI at build time; in
egress-restricted environments set
`SWAGGER_UI_DOWNLOAD_URL=file:///path/to/swagger-ui-5.17.14.zip` (repackage the
npm `swagger-ui-dist` tarball as `swagger-ui-5.17.14/dist/*`).

Run the e2e suite: `tests/uc-compat/run.sh` (MODE=allowall | openfga) — see
`tests/uc-compat/README.md` in the fork.

## v1 scope notes

No Delta managed commits (protocol-level work, out of scope), no
temporary-path-credentials, hard deletes (no soft-delete/undrop for UC
entities), no rename for volumes/models, catalogs read-only via UC surface,
no events/idempotency records on UC endpoints (schemas excepted via
delegation). Full list in the fork's `docs/docs/uc-compat.md`.
