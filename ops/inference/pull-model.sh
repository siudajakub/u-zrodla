#!/bin/sh
# Jednorazowe pobranie obrazu i wag do lokalnej Ollamy w Compose.
#   sh ops/inference/pull-model.sh [MODEL]
# Domyślne miejsce wag: .runtime/ollama (konfiguracja: INVESTWATCH_OLLAMA_DIR).
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
. "$ROOT/ops/demo/common.sh"
iw_load_env
MODEL=${1:-${INVESTWATCH_SECOND_OPINION_MODEL:-${INVESTWATCH_LLM_MODEL:-qwen3.5:4b-q4_K_M}}}
IMAGE=${INVESTWATCH_OLLAMA_IMAGE:-ollama/ollama:0.40.17}
OLLAMA_DIR=${INVESTWATCH_OLLAMA_DIR:-$ROOT/.runtime/ollama}
case "$OLLAMA_DIR" in /*) ;; *) OLLAMA_DIR="$ROOT/$OLLAMA_DIR" ;; esac
mkdir -p "$OLLAMA_DIR"
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE"
# Pobranie w oddzielnym kontenerze nie zmienia sieci działającej instancji.
docker run --rm --user "$(id -u):$(id -g)" --volume "$OLLAMA_DIR:/models" \
  --env HOME=/models --env OLLAMA_MODELS=/models/models \
  --entrypoint /bin/sh "$IMAGE" -eu -c '
    ollama serve &
    server=$!
    trap "kill $server 2>/dev/null || true" EXIT
    i=0
    until ollama list >/dev/null 2>&1; do
      i=$((i + 1))
      [ "$i" -lt 30 ] || { echo "Ollama nie odpowiada." >&2; exit 1; }
      sleep 1
    done
    ollama pull "$1"
  ' sh "$MODEL"
echo "Pobrano $MODEL. Uruchom sh ops/demo/start.sh."
