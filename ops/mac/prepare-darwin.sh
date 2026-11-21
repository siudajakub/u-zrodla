#!/bin/sh
# macOS (Apple Silicon): przygotowanie stanowiska w kontenerze linux/arm64. Wolane z ops/demo/bootstrap.sh.
# Host nie buduje kol ani FFmpeg, bo kontenery montuja .runtime i potrzebuja ELF aarch64, nie Mach-O.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$root"
image=python:3.12-bookworm
command -v docker >/dev/null 2>&1 || { echo 'Zainstaluj Docker Desktop (lub OrbStack).' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Demon Docker nie odpowiada. Uruchom Docker Desktop.' >&2; exit 1; }
arch=$(docker image inspect "$image" --format '{{.Architecture}}' 2>/dev/null || true)
if [ "$arch" != arm64 ]; then
  docker pull --platform linux/arm64 "$image"
  arch=$(docker image inspect "$image" --format '{{.Architecture}}' 2>/dev/null || true)
fi
[ "$arch" = arm64 ] || { echo "Obraz $image ma architekture '$arch', potrzebna arm64." >&2; exit 1; }
mkdir -p .runtime/build/tmp .runtime/build/cache .runtime/build/wheels .runtime/watch .runtime/semantic .runtime/asr
docker run --rm --platform linux/arm64 --pull never \
  -e PREPARE_UID="$(id -u)" -e PREPARE_GID="$(id -g)" \
  -v "$root:/work" -w /work "$image" sh ops/mac/container-prepare.sh
sh ops/mac/arch-guard.sh aarch64 .runtime/demo/deps .runtime/semantic/deps .runtime/asr/vosk
