#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
[ -f .runtime/demo/compose.env ] || exec sh ops/demo/bootstrap.sh
exec docker compose --env-file .runtime/demo/compose.env -f compose.yaml up -d --no-build --pull never
