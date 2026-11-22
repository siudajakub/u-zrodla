#!/bin/sh
# Czeka na ukończony skan źródeł. Pusta kolejka jest poprawnym wynikiem.
# Użycie: sh ops/demo/wait-ready.sh PORT [demo|live] [SEKUNDY].
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
. "$ROOT/ops/demo/common.sh"
iw_python || exit 1
port=${1:-8769}; mode=${2:-demo}; max=${3:-900}
min_scans=2
[ "$mode" != live ] || min_scans=1
t0=$(date +%s)
while :; do
  rc=0; line=$("$PY3" "$ROOT/ops/demo/queue_status.py" --port "$port" --min-scans "$min_scans") || rc=$?
  now=$(date +%s); el=$((now - t0))
  if [ "$rc" = 0 ]; then echo "GOTOWE po ${el}s: $line"; exit 0; fi
  if [ "$el" -ge "$max" ]; then
    echo "Po ${el}s: $line"
    echo 'Brak potwierdzenia ukończonego skanu. Sprawdź logi API i workera.' >&2; exit 1
  fi
  [ $((el % 30)) -lt 3 ] && [ "$el" -gt 0 ] && echo "... ${el}s: $line"
  sleep 3
done
