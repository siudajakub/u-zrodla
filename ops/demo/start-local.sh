#!/bin/sh
# Wariant awaryjny bez Dockera: ten sam stan i ta sama paczka mediów, API (uvicorn) i worker jako procesy hosta.
# macOS arm64 i Linux x86_64, Python 3.12, POSIX sh. Dane: .runtime/local/state, logi i pidy: .runtime/local/.
#   sh ops/demo/start-local.sh            start (tryb pokazu), czeka na kolejkę z 4 filmami
#   sh ops/demo/start-local.sh --live     tryb live (harmonogram co INVESTWATCH_DISCOVERY_INTERVAL s, domyślnie 14400)
#   sh ops/demo/start-local.sh --reset    czysty stan
#   sh ops/demo/start-local.sh --stop     zatrzymuje oba procesy
# Zmienne: INVESTWATCH_PORT (8769), INVESTWATCH_LOCAL_DIR (.runtime/local), INVESTWATCH_PREVIEW=off, patrz .env.example.
# Pierwszy start tworzy venv (.runtime/venv-local) i instaluje api/requirements.lock (potrzebna sieć tylko wtedy).
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
. "$ROOT/ops/demo/common.sh"
RESET=${INVESTWATCH_RESET:-0}; WAIT=1; STOP=0
for a in "$@"; do
  case "$a" in
    --live) INVESTWATCH_MODE=live ;;
    --demo) INVESTWATCH_MODE=demo ;;
    --reset) RESET=1 ;;
    --stop) STOP=1 ;;
    --no-wait) WAIT=0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Nieznana opcja: $a" >&2; exit 2 ;;
  esac
done
iw_load_env
DIR=${INVESTWATCH_LOCAL_DIR:-$ROOT/.runtime/local}
PORT=${INVESTWATCH_PORT:-8769}
stop_all() {
  for n in worker api; do
    if [ -f "$DIR/$n.pid" ]; then
      pid=$(cat "$DIR/$n.pid")
      if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; i=0
        while kill -0 "$pid" 2>/dev/null && [ $i -lt 20 ]; do sleep 0.5; i=$((i+1)); done
        kill -9 "$pid" 2>/dev/null || true
      fi
      rm -f "$DIR/$n.pid"
    fi
  done
}
mkdir -p "$DIR"
if [ "$STOP" = 1 ]; then stop_all; echo 'Zatrzymano.'; exit 0; fi
MODE=${INVESTWATCH_MODE:-demo}
case "$MODE" in
  demo) INTERVAL=0 ;;
  live) INTERVAL=${INVESTWATCH_DISCOVERY_INTERVAL:-14400}; [ "$INTERVAL" -gt 0 ] || INTERVAL=14400 ;;
  *) echo "INVESTWATCH_MODE musi być demo albo live." >&2; exit 2 ;;
esac
iw_need_pack
iw_python
[ -n "$PY312" ] || { echo 'Wymagany Python 3.12 (macOS: brew install python@3.12, potem uruchom ponownie).' >&2; exit 1; }
stop_all
if [ "$RESET" = 1 ]; then rm -rf "$DIR/state"; echo "Stan wyczyszczony ($DIR/state)."; fi
mkdir -p "$DIR/state" "$ROOT/.runtime/semantic"; chmod 700 "$DIR/state"

VENV=$ROOT/.runtime/venv-local
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c 'import fastapi,huey,uvicorn' 2>/dev/null; then
  echo 'Przygotowuję venv (jednorazowo)...'
  [ -x "$VENV/bin/python" ] || "$PY312" -m venv "$VENV"
  links=; [ ! -d "$ROOT/.runtime/build/wheels" ] || links="--find-links $ROOT/.runtime/build/wheels"
  # shellcheck disable=SC2086
  "$VENV/bin/pip" install --disable-pip-version-check --prefer-binary $links -r api/requirements.lock
fi
# E5 (podpowiedzi M3) jest opcjonalne: bez pakietów lub wag M3 działa tylko regułami (stan: semantic.status).
if ! "$VENV/bin/python" -c 'import numpy,onnxruntime,tokenizers' 2>/dev/null && [ -f analysis/semantic-requirements.txt ]; then
  "$VENV/bin/pip" install --disable-pip-version-check --prefer-binary -r analysis/semantic-requirements.txt >"$DIR/semantic-pip.log" 2>&1 ||
    echo 'Uwaga: nie zainstalowano pakietów E5 (zobacz '"$DIR"'/semantic-pip.log). M3 będzie działać tylko regułami.' >&2
fi
if [ ! -f .runtime/semantic/model_quantized.onnx ]; then
  "$VENV/bin/python" -m analysis.setup_semantic >"$DIR/semantic-weights.log" 2>&1 ||
    echo 'Uwaga: brak wag E5 (wymaga sieci). M3 będzie działać tylko regułami.' >&2
fi
if [ "$MODE" = live ]; then # media z YouTube (yt-dlp, napisy): tylko w trybie lokalnym, obraz Compose ich nie ma
  "$VENV/bin/python" -c 'import yt_dlp,youtube_transcript_api' 2>/dev/null ||
    "$VENV/bin/pip" install --disable-pip-version-check -r ops/demo/live-requirements.txt ||
    echo 'Uwaga: nie zainstalowano yt-dlp i youtube-transcript-api; media live będą lukami pokrycia.' >&2
  export PATH="$VENV/bin:$PATH"
fi
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  sh ops/demo/prepare-preview.sh --offline >"$DIR/preview.log" 2>&1 || sh ops/demo/prepare-preview.sh --prepare >"$DIR/preview.log" 2>&1 ||
    echo "Podgląd Astryx nie został zbudowany ($DIR/preview.log). Pulpit pod / działa." >&2
fi

export INVESTWATCH_STATE="$DIR/state" INVESTWATCH_REPLAY_MEDIA="$(iw_pack_dir)" INVESTWATCH_DISCOVERY_INTERVAL="$INTERVAL"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT"
nohup "$VENV/bin/python" -m uvicorn api.server:app --host 127.0.0.1 --port "$PORT" >"$DIR/api.log" 2>&1 &
echo $! > "$DIR/api.pid"
nohup "$VENV/bin/python" -m api.worker >"$DIR/worker.log" 2>&1 &
echo $! > "$DIR/worker.pid"
echo "Tryb: $MODE (harmonogram live: $INTERVAL s). API pid $(cat "$DIR/api.pid"), worker pid $(cat "$DIR/worker.pid"). Pulpit: http://127.0.0.1:$PORT/"
echo "Zatrzymanie: sh ops/demo/start-local.sh --stop"
[ "$WAIT" = 1 ] || exit 0
exec sh ops/demo/wait-ready.sh "$PORT" "$MODE"
