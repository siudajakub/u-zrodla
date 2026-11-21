#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
[ -f .runtime/demo/compose.env ] || exec sh ops/demo/bootstrap.sh
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  if ! sh ops/demo/prepare-preview.sh --offline > .runtime/demo/preview.log 2>&1; then
    echo 'Podgląd Astryx nie został odświeżony. Zobacz .runtime/demo/preview.log. Otwórz pulpit pod /.' >&2
  fi
fi
exec docker compose --env-file .runtime/demo/compose.env -f compose.yaml up -d --no-build --pull never
