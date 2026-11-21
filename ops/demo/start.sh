#!/bin/sh
# Jedna komenda do pulpitu z kolejką "Co wymaga sprawdzenia" (4 znane filmy z datowanego replay 21 XI).
#   sh ops/demo/start.sh            tryb pokazu: replay, bez sieci, bez harmonogramu live
#   sh ops/demo/start.sh --live     tryb live: harmonogram skanu co 4 h (INVESTWATCH_DISCOVERY_INTERVAL), klucz YouTube z .env
#   sh ops/demo/start.sh --reset    czysty stan (kasuje .runtime/demo/state) i start od zera
#   sh ops/demo/start.sh --no-wait  bez czekania na kolejkę
# Zmienne (także w .env, wzór: .env.example): INVESTWATCH_MODE=demo|live, INVESTWATCH_PORT, INVESTWATCH_REPLAY_MEDIA,
# INVESTWATCH_MEDIA_ARCHIVE, INVESTWATCH_STATE_DIR (inny katalog stanu), COMPOSE_PROJECT_NAME, YOUTUBE_API_KEY, INVESTWATCH_PREVIEW=off.
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
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
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
if [ "$RESET" = 1 ] && [ -f .runtime/demo/compose.env ]; then
  docker compose --env-file .runtime/demo/compose.env -f compose.yaml down --timeout 3 >/dev/null 2>&1 || true
  state=${INVESTWATCH_STATE_DIR:-$ROOT/.runtime/demo/state}
  rm -rf "$state"; mkdir -p "$state"; chmod 700 "$state"
  echo "Stan wyczyszczony ($state)."
fi
INVESTWATCH_RESET=0; export INVESTWATCH_RESET INVESTWATCH_MODE="$MODE"
[ -f .runtime/demo/compose.env ] || exec sh ops/demo/bootstrap.sh
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  if ! sh ops/demo/prepare-preview.sh --offline > .runtime/demo/preview.log 2>&1; then
    echo 'Podgląd Astryx nie został odświeżony. Zobacz .runtime/demo/preview.log. Otwórz pulpit pod /.' >&2
  fi
fi
docker compose --env-file .runtime/demo/compose.env -f compose.yaml up -d --no-build --pull never
PORT=${INVESTWATCH_PORT:-8769}
echo "Tryb: $MODE (harmonogram live: $INVESTWATCH_DISCOVERY_INTERVAL s). Pulpit: http://127.0.0.1:$PORT/"
[ "$WAIT" = 1 ] || exit 0
exec sh ops/demo/wait-ready.sh "$PORT" "$MODE"
