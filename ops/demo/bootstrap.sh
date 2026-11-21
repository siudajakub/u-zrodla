#!/bin/sh
# Prepare this machine once, then start the same offline-ready services as start.sh.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$root"
mode=host
[ "${1:-}" != --in-container ] || mode=container
if [ -d /home/codexdev/projects/.vps-runtime ]; then
  mountpoint -q /home/codexdev/projects
  case "$root" in /home/codexdev/projects/*) ;; *) echo 'Wymagany wolumen projektów na devbox.' >&2; exit 1;; esac
  [ "$(df -Pk "$root" | awk 'NR==2{print $4}')" -ge 10485760 ]
  [ "$(df -Pk / | awk 'NR==2{print $4}')" -ge 5242880 ]
fi
if [ "$mode" = host ] && [ "$(uname -s)" = Darwin ]; then
  # macOS: kola, Vosk, E5 i FFmpeg powstaja w kontenerze linux/arm64 (ops/mac/prepare-darwin.sh).
  sh ops/mac/prepare-darwin.sh
else
command -v ffmpeg >/dev/null
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Wymagany Python 3.12"'
mkdir -p .runtime/build/tmp .runtime/build/cache .runtime/build/wheels .runtime/watch .runtime/semantic
export TMPDIR="$root/.runtime/build/tmp" PIP_CACHE_DIR="$root/.runtime/build/cache"
venv=.runtime/venv
if [ "$mode" = container ]; then venv=.runtime/venv-container; export PREPARE_PYTHON="$root/$venv/bin/python"; fi
if [ ! -x "$venv/bin/python" ]; then python3 -m venv "$venv"; fi
"$venv/bin/pip" wheel --disable-pip-version-check --wheel-dir .runtime/build/wheels -r api/requirements.lock
"$venv/bin/python" -m analysis.setup_asr
if [ -f analysis/semantic-requirements.txt ]; then
  mkdir -p .runtime/semantic/wheels
  "$venv/bin/pip" wheel --disable-pip-version-check --wheel-dir .runtime/semantic/wheels -r analysis/semantic-requirements.txt
  "$venv/bin/pip" install --no-index --find-links .runtime/semantic/wheels --target .runtime/semantic/deps -r analysis/semantic-requirements.txt
  "$venv/bin/python" -m analysis.setup_semantic
fi
if [ "$mode" = host ]; then docker image inspect python:3.12-bookworm >/dev/null 2>&1 || docker pull python:3.12-bookworm; fi
sh ops/demo/prepare.sh
[ "$mode" = host ] || exit 0
fi
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  sh ops/demo/prepare-preview.sh --prepare > .runtime/demo/preview.log 2>&1 ||
    echo 'Nie przygotowano podglądu Astryx. Zobacz .runtime/demo/preview.log.' >&2
  exec env INVESTWATCH_PREVIEW=off sh ops/demo/start.sh
fi
exec sh ops/demo/start.sh
