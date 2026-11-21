#!/bin/sh
# Prepare this machine once, then start the same offline-ready services as start.sh.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$root"
if [ -d /home/codexdev/projects/.vps-runtime ]; then
  mountpoint -q /home/codexdev/projects
  case "$root" in /home/codexdev/projects/*) ;; *) echo 'Wymagany wolumen projektów na devbox.' >&2; exit 1;; esac
  [ "$(df -Pk "$root" | awk 'NR==2{print $4}')" -ge 10485760 ]
  [ "$(df -Pk / | awk 'NR==2{print $4}')" -ge 5242880 ]
fi
command -v ffmpeg >/dev/null
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Wymagany Python 3.12"'
mkdir -p .runtime/build/tmp .runtime/build/cache .runtime/build/wheels .runtime/watch .runtime/semantic
export TMPDIR="$root/.runtime/build/tmp" PIP_CACHE_DIR="$root/.runtime/build/cache"
if [ ! -x .runtime/venv/bin/python ]; then python3 -m venv .runtime/venv; fi
.runtime/venv/bin/pip wheel --disable-pip-version-check --wheel-dir .runtime/build/wheels -r api/requirements.lock
.runtime/venv/bin/python -m analysis.setup_asr
if [ -f analysis/semantic-requirements.txt ]; then
  mkdir -p .runtime/semantic/wheels
  .runtime/venv/bin/pip wheel --disable-pip-version-check --wheel-dir .runtime/semantic/wheels -r analysis/semantic-requirements.txt
  .runtime/venv/bin/pip install --no-index --find-links .runtime/semantic/wheels --target .runtime/semantic/deps -r analysis/semantic-requirements.txt
  .runtime/venv/bin/python -m analysis.setup_semantic
fi
docker image inspect python:3.12-bookworm >/dev/null 2>&1 || docker pull python:3.12-bookworm
sh ops/demo/prepare.sh
if [ "${INVESTWATCH_PREVIEW:-auto}" != off ] && [ -f web/package-lock.json ]; then
  sh ops/demo/prepare-preview.sh --prepare > .runtime/demo/preview.log 2>&1 ||
    echo 'Nie przygotowano podglądu Astryx. Zobacz .runtime/demo/preview.log.' >&2
  exec env INVESTWATCH_PREVIEW=off sh ops/demo/start.sh
fi
exec sh ops/demo/start.sh
