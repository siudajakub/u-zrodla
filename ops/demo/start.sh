#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
[ -f .runtime/demo/compose.env ] || { echo 'Najpierw uruchom sh ops/demo/prepare.sh.' >&2; exit 1; }
[ -f compose.yaml ] || { echo 'Skopiuj ops/demo/compose.yaml do compose.yaml w katalogu repozytorium.' >&2; exit 1; }
exec docker compose --project-directory "$ROOT" --env-file .runtime/demo/compose.env -f compose.yaml up -d --no-build --pull never
