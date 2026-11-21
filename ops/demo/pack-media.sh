#!/bin/sh
# Pakuje paczkę mediów replay (.runtime/replay-media/2026-11-21) do przenośnego archiwum tar.gz + SHA-256.
# Archiwum jest poza Gitem. Na docelowym komputerze położ oba pliki w katalogu projektu i uruchom ops/demo/start.sh.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
. "$ROOT/ops/demo/common.sh"
iw_python || exit 1
pack=$(iw_pack_dir)
IW_LOG="$ROOT/.runtime/pack-verify.log"; mkdir -p "$ROOT/.runtime/dist"
iw_pack_verify "$pack" || { echo "Paczka $pack nie przechodzi weryfikacji:"; cat "$IW_LOG"; exit 1; }
out="${1:-$ROOT/.runtime/dist}"; mkdir -p "$out"
parent=$(dirname "$pack"); name=$(basename "$pack")
case "$name" in "$EVENT") ;; *) echo "Oczekiwano katalogu o nazwie $EVENT." >&2; exit 1 ;; esac
tmp="$ROOT/.runtime/pack-stage"; rm -rf "$tmp"; mkdir -p "$tmp/replay-media"
cp -R "$pack" "$tmp/replay-media/$EVENT"
COPYFILE_DISABLE=1 tar -czf "$out/$ARCHIVE_NAME" -C "$tmp" replay-media
rm -rf "$tmp"
(cd "$out" && iw_sha "$ARCHIVE_NAME" > "$ARCHIVE_NAME.sha256")
ls -l "$out/$ARCHIVE_NAME" "$out/$ARCHIVE_NAME.sha256"
cat "$out/$ARCHIVE_NAME.sha256"
echo "Skopiuj oba pliki do katalogu projektu na komputerze pokazu (np. scp lub pendrive)."
