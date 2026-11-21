#!/bin/sh
# Uruchamiane WEWNATRZ kontenera python:3.12-bookworm (linux/arm64) przez ops/mac/prepare-darwin.sh.
# Robi to, co na Linuksie robi bootstrap.sh na hoscie: koła, Vosk, E5 i prywatna kopia FFmpeg
# powstaja w architekturze kontenera. Wymaga: /work = katalog projektu, siec, uzytkownik root.
set -eu
cd /work
: "${PREPARE_UID:?}" "${PREPARE_GID:?}"
if ! command -v ffmpeg >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends ffmpeg
fi
status=0
sh ops/demo/bootstrap.sh --in-container || status=$?
for d in .runtime/demo .runtime/asr .runtime/semantic .runtime/build .runtime/venv-container .runtime/watch; do
  [ ! -e "$d" ] || chown -R "$PREPARE_UID:$PREPARE_GID" "$d" || echo "Uwaga: nie zmieniono wlasciciela $d" >&2
done
exit "$status"
