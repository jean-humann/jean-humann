#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# Check ownership before creating configs or environments.
for kind in container volume network; do
  resource_ids="$(docker "$kind" ls -q --filter label=com.docker.compose.project=hemera-v2-review)"
  if [ "$kind" = container ]; then
    resource_ids="$(docker container ls -aq --filter label=com.docker.compose.project=hemera-v2-review)"
  fi
  if [ -n "$resource_ids" ]; then
    printf 'Existing bench %s resources detected; inspect and clean the owned bench first.\n' "$kind" >&2
    exit 1
  fi
done
for resource in db keycloak openfga-migrate openfga storage migrate lakekeeper spark client; do
  if docker container inspect "hemera-v2-review-$resource" >/dev/null 2>&1; then
    printf 'Container name collision: hemera-v2-review-%s\n' "$resource" >&2
    exit 1
  fi
done
for resource in db storage; do
  if docker volume inspect "hemera-v2-review_$resource" >/dev/null 2>&1; then
    printf 'Volume name collision: hemera-v2-review_%s\n' "$resource" >&2
    exit 1
  fi
done
if docker network inspect hemera-v2-review_default >/dev/null 2>&1; then
  printf 'Network name collision: hemera-v2-review_default\n' >&2
  exit 1
fi
mkdir -p evidence jars
python3 scripts/prepare.py
uv venv --python 3.12.13 venv
uv pip install --python venv/bin/python -r requirements-host.txt
uv venv --python 3.10.19 spark-client-venv
uv pip install --python spark-client-venv/bin/python -r requirements-spark.txt
uv venv --python 3.10.19 full-client-venv
uv pip install --python full-client-venv/bin/python -r requirements-full.txt
for artifact in iceberg-spark-runtime-4.1_2.13 iceberg-aws-bundle; do
  curl --fail --location --silent --show-error "https://repo.maven.apache.org/maven2/org/apache/iceberg/$artifact/1.11.0/$artifact-1.11.0.jar" -o "jars/$artifact-1.11.0.jar"
done
shasum -a 256 -c jars.sha256
trap 'bash "$ROOT_DIR/scripts/cleanup.sh"' EXIT
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review up -d db keycloak storage
venv/bin/python - <<'PY'
import requests,time
for attempt in range(120):
 try:
  r=requests.get('http://127.0.0.1:18080/realms/hemera-v2-review/.well-known/openid-configuration',timeout=2)
  if r.status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
else:raise SystemExit('Keycloak startup timeout')
PY
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review up -d openfga-migrate openfga migrate lakekeeper
venv/bin/python - <<'PY'
import requests,time
for attempt in range(120):
 try:
  if requests.get('http://127.0.0.1:18181/health',timeout=2).status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
else:raise SystemExit('Lakekeeper startup timeout')
PY
venv/bin/python scripts/bootstrap.py
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review --profile client run --rm --no-deps client /bin/sh -c 'python -m venv /lab/linux-venv && /lab/linux-venv/bin/pip install -r /lab/requirements-catalog.txt'
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review --profile client run --rm --no-deps client /lab/linux-venv/bin/python -u /lab/scripts/catalog_campaigns.py >evidence/catalog-run.log 2>&1
venv/bin/python scripts/native_ttl_probe.py
venv/bin/python scripts/queue_campaign.py
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review --profile spark up -d spark
venv/bin/python - <<'PY'
import socket,time
for attempt in range(120):
 try:
  with socket.create_connection(('127.0.0.1',15003),timeout=1):break
 except OSError:time.sleep(1)
else:raise SystemExit('Spark startup timeout')
PY
spark-client-venv/bin/python scripts/spark_campaigns.py >evidence/spark-run.log 2>&1
spark-client-venv/bin/python scripts/strict_golden.py
venv/bin/python scripts/client_parity.py
spark-client-venv/bin/python scripts/schema_transition.py
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review --profile client run --rm --no-deps client /lab/linux-venv/bin/python -u /lab/scripts/staging_isolation.py >evidence/staging-isolation.log 2>&1
venv/bin/python scripts/summarize.py
printf 'Probes completed. Read evidence/results.json; execution success does not imply acceptance.\n'
