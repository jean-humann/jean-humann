#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Refuse cleanup if a same-name container does not have our bench label.
for service in db keycloak openfga-migrate openfga storage migrate lakekeeper spark client; do
  resource="hemera-v2-review-$service"
  if docker container inspect "$resource" >/dev/null 2>&1; then
    bench_label="$(docker container inspect "$resource" --format '{{index .Config.Labels "hemera-v2-review"}}')"
    if [ "$bench_label" != true ]; then
      printf 'Refusing cleanup: %s has no bench ownership label.\n' "$resource" >&2
      exit 1
    fi
  fi
done
# Include stopped/one-off containers and all project volumes/networks.
for kind in container volume network; do
  if [ "$kind" = container ]; then
    resource_ids="$(docker container ls -aq --filter label=com.docker.compose.project=hemera-v2-review)"
  else
    resource_ids="$(docker "$kind" ls -q --filter label=com.docker.compose.project=hemera-v2-review)"
  fi
  for resource in $resource_ids; do
    if [ "$kind" = container ]; then
      label_template='{{index .Config.Labels "hemera-v2-review"}}'
    else
      label_template='{{index .Labels "hemera-v2-review"}}'
    fi
    bench_label="$(docker "$kind" inspect "$resource" --format "$label_template")"
    if [ "$bench_label" != true ]; then
      printf 'Refusing cleanup: %s %s has no bench ownership label.\n' "$kind" "$resource" >&2
      exit 1
    fi
  done
done
for resource in db storage; do
  name="hemera-v2-review_$resource"
  if docker volume inspect "$name" >/dev/null 2>&1; then
    bench_label="$(docker volume inspect "$name" --format '{{index .Labels "hemera-v2-review"}}')"
    if [ "$bench_label" != true ]; then
      printf 'Refusing cleanup: volume %s is not owned by this bench.\n' "$name" >&2
      exit 1
    fi
  fi
done
if docker network inspect hemera-v2-review_default >/dev/null 2>&1; then
  bench_label="$(docker network inspect hemera-v2-review_default --format '{{index .Labels "hemera-v2-review"}}')"
  if [ "$bench_label" != true ]; then
    printf 'Refusing cleanup: network hemera-v2-review_default is not owned by this bench.\n' >&2
    exit 1
  fi
fi
docker compose -f "$ROOT_DIR/compose.yaml" -p hemera-v2-review --profile spark --profile client down --volumes
