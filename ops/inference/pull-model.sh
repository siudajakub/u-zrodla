#!/bin/sh
# Jednorazowe pobranie wag do serwisu inference (profil Compose `llm`, Linux z dużą pamięcią).
#   sh ops/inference/pull-model.sh [MODEL]     domyślnie INVESTWATCH_LLM_MODEL albo qwen3.5:4b-q4_K_M
# Wagi trafiają do INVESTWATCH_OLLAMA_DIR (domyślnie .runtime/ollama, poza Gitem). Potrzebny Internet tylko teraz.
# Mac: Ollamę uruchom natywnie na hoście (Metal), a nie w kontenerze — patrz ops/mac/README.md.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
. "$ROOT/ops/demo/common.sh"
iw_load_env
MODEL=${1:-${INVESTWATCH_LLM_MODEL:-qwen3.5:4b-q4_K_M}}
IMAGE=${INVESTWATCH_OLLAMA_IMAGE:-ollama/ollama:0.40.17}
[ -f .runtime/demo/compose.env ] || { echo 'Najpierw sh ops/demo/start.sh (tworzy .runtime/demo/compose.env).' >&2; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE"
mkdir -p "${INVESTWATCH_OLLAMA_DIR:-$ROOT/.runtime/ollama}"
dc() { docker compose --env-file .runtime/demo/compose.env -f compose.yaml -f ops/inference/pull.yaml --profile llm "$@"; }
dc up -d --no-deps --pull never inference
trap 'dc stop inference >/dev/null 2>&1 || true' EXIT
i=0; until dc exec -T inference ollama list >/dev/null 2>&1; do i=$((i+1)); [ $i -lt 30 ] || exit 1; sleep 1; done
dc exec -T inference ollama pull "$MODEL"
dc exec -T inference ollama list
echo "Gotowe. Włącz: INVESTWATCH_LLM=1 INVESTWATCH_LLM_MODEL=$MODEL COMPOSE_PROFILES=llm sh ops/demo/start.sh"
