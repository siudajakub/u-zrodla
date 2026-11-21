#!/bin/sh
# Archiwum gotowego stanu pokazu po zakończonym bootstrapie: SQLite (spójna kopia) + magazyn obiektów,
# suma SHA-256 i odcisk wersji kodu. start.sh / start-local.sh rozpakują je zamiast liczyć ~1,4 tys. materiałów.
#   sh ops/demo/pack-state.sh            stan Compose (.runtime/demo/state + .runtime/demo/objects)
#   sh ops/demo/pack-state.sh --local    stan wariantu bez Dockera (.runtime/local/state)
# Wynik: .runtime/dist/investwatch-state-2026-11-21.tar.gz i .sha256. Skopiuj OBA do katalogu projektu na pokazie.
# Archiwum pasuje tylko do tej samej zawartości api/ analysis/ collectors/ fixtures/ data/probe-snapshots/.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
. "$ROOT/ops/demo/common.sh"
iw_load_env
iw_python || exit 1
FLAVOR=compose
for a in "$@"; do
  case "$a" in
    --local) FLAVOR=local ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "Nieznana opcja: $a" >&2; exit 2 ;;
  esac
done
if [ "$FLAVOR" = local ]; then
  STATE_DIR=${INVESTWATCH_LOCAL_DIR:-$ROOT/.runtime/local}/state; OBJECTS_DIR=$STATE_DIR
else
  iw_state_dirs
fi
OUT=${INVESTWATCH_STATE_ARCHIVE_OUT:-$ROOT/.runtime/dist/$STATE_ARCHIVE_NAME}
umask 077
"$PY3" ops/demo/state_pack.py pack --state "$STATE_DIR" --objects "$OBJECTS_DIR" --out "$OUT" --flavor "$FLAVOR"
echo "Na komputerze pokazu połóż $STATE_ARCHIVE_NAME i .sha256 w katalogu projektu, potem: sh ops/demo/start.sh --reset"
