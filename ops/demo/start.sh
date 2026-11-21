#!/bin/sh
# Jedna komenda do pulpitu z kolejką "Co wymaga sprawdzenia" (4 znane filmy z datowanego replay 21 XI).
#   sh ops/demo/start.sh            tryb pokazu: replay, bez sieci, bez harmonogramu live
#   sh ops/demo/start.sh --live     tryb live: harmonogram skanu co 4 h (INVESTWATCH_DISCOVERY_INTERVAL), klucz YouTube z .env
#   sh ops/demo/start.sh --reset    czysty stan (kasuje .runtime/demo/state) i start od zera
#   sh ops/demo/start.sh --no-wait  bez czekania na kolejkę
# Serwisy: web (jedyny port), api, worker; --live dokłada scheduler i wyjście do sieci dla workera (ops/compose/egress.yaml).
# Zmienne (także w .env, wzór: .env.example): INVESTWATCH_MODE=demo|live, INVESTWATCH_PORT, INVESTWATCH_REPLAY_MEDIA,
# INVESTWATCH_MEDIA_ARCHIVE, INVESTWATCH_STATE_DIR, INVESTWATCH_OBJECTS_DIR,
# COMPOSE_PROJECT_NAME, COMPOSE_PROFILES (np. llm), OLLAMA_HOST, YOUTUBE_API_KEY, INVESTWATCH_PREVIEW=off.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
. "$ROOT/ops/demo/common.sh"
RESET=${INVESTWATCH_RESET:-0}; WAIT=1
for a in "$@"; do
  case "$a" in
    --live) INVESTWATCH_MODE=live ;;
    --demo) INVESTWATCH_MODE=demo ;;
    --reset) RESET=1 ;;
    --no-wait) WAIT=0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Nieznana opcja: $a" >&2; exit 2 ;;
  esac
done
iw_load_env
MODE=${INVESTWATCH_MODE:-demo}
case "$MODE" in
  demo) INVESTWATCH_DISCOVERY_INTERVAL=0 ;;
  live) INVESTWATCH_DISCOVERY_INTERVAL=${INVESTWATCH_DISCOVERY_INTERVAL:-14400}
        [ "$INVESTWATCH_DISCOVERY_INTERVAL" -gt 0 ] || INVESTWATCH_DISCOVERY_INTERVAL=14400 ;;
  *) echo "INVESTWATCH_MODE musi być demo albo live." >&2; exit 2 ;;
esac
export INVESTWATCH_DISCOVERY_INTERVAL
iw_need_pack
INVESTWATCH_MEDIA_PACK=$(iw_pack_dir); export INVESTWATCH_MEDIA_PACK
iw_state_dirs
FILES="-f compose.yaml"
case "$MODE:${OLLAMA_HOST:-}" in live:*|*host.docker.internal*) FILES="$FILES -f ops/compose/egress.yaml" ;; esac
[ "$MODE" != live ] || { COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}live"; export COMPOSE_PROFILES; }
# shellcheck disable=SC2086
dc() { docker compose --env-file .runtime/demo/compose.env $FILES "$@"; }
if [ "$RESET" = 1 ] && [ -f .runtime/demo/compose.env ]; then
  dc --profile '*' down --timeout 3 >/dev/null 2>&1 || dc down --timeout 3 >/dev/null 2>&1 || true
  rm -rf "$STATE_DIR" "$OBJECTS_DIR"; mkdir -p "$STATE_DIR"; chmod 700 "$STATE_DIR"
  echo "Stan wyczyszczony ($STATE_DIR, $OBJECTS_DIR)."
fi
INVESTWATCH_RESET=0; export INVESTWATCH_RESET INVESTWATCH_MODE="$MODE"
[ -f .runtime/demo/compose.env ] || exec sh ops/demo/bootstrap.sh
mkdir -p "$STATE_DIR"; chmod 700 "$STATE_DIR"
iw_objects_layout "$STATE_DIR" "$OBJECTS_DIR"
case ",${COMPOSE_PROFILES:-}," in *,llm,*) mkdir -p "${INVESTWATCH_OLLAMA_DIR:-$ROOT/.runtime/ollama}" ;; esac
WEB_IMAGE=${INVESTWATCH_WEB_IMAGE:-nginx:1.27-alpine}
docker image inspect "$WEB_IMAGE" >/dev/null 2>&1 || docker pull "$WEB_IMAGE"
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  if ! sh ops/demo/prepare-preview.sh --offline > .runtime/demo/preview.log 2>&1; then
    echo 'Podgląd Astryx nie został odświeżony. Zobacz .runtime/demo/preview.log. Otwórz pulpit pod /.' >&2
  fi
fi
[ "$MODE" = live ] || dc --profile live rm -sf scheduler >/dev/null 2>&1 || true
dc up -d --no-build --pull never
PORT=${INVESTWATCH_PORT:-8769}
echo "Tryb: $MODE (harmonogram live: $INVESTWATCH_DISCOVERY_INTERVAL s). Pulpit: http://127.0.0.1:$PORT/"
[ "$WAIT" = 1 ] || exit 0
exec sh ops/demo/wait-ready.sh "$PORT" "$MODE"
