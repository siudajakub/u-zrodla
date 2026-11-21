#!/bin/sh
# Pierwszy start liczy ok. 1300 materiałów z replay YouTube (minuty, zależnie od CPU). Czeka, aż skany bootstrapu (m2 + youtube replay) się zakończą, i sprawdza kolejkę "Co wymaga sprawdzenia".
# Użycie: sh ops/demo/wait-ready.sh PORT [demo|live] [SEKUNDY]. W trybie demo kolejka musi zawierać 4 znane filmy
# (obok nich mogą być oferty M2/M3; kod 4 przy braku). INVESTWATCH_EXPECT_EXACT=1 wymaga dokładnie tych 4 pozycji.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
. "$ROOT/ops/demo/common.sh"
iw_python || exit 1
port=${1:-8769}; mode=${2:-demo}; max=${3:-900}
extra=
if [ "$mode" = demo ]; then
  if [ "${INVESTWATCH_EXPECT_EXACT:-0}" = 1 ]; then extra="--expect-count 4"; else extra="--require-ids known"; fi
fi
t0=$(date +%s)
while :; do
  rc=0; line=$("$PY3" "$ROOT/ops/demo/queue_status.py" --port "$port" $extra) || rc=$?
  now=$(date +%s); el=$((now - t0))
  if [ "$rc" = 0 ]; then echo "GOTOWE po ${el}s: $line"; exit 0; fi
  if [ "$el" -ge "$max" ]; then
    echo "Po ${el}s: $line"
    if [ "$mode" = demo ] && echo "$line" | grep -q 'busy=0'; then
      echo 'Kolejka review nie zawiera 4 znanych filmów. Sprawdź paczkę mediów (python3 -m api.replay_pack verify) i logi workera.' >&2; exit 4
    fi
    echo 'Skany jeszcze trwają albo API nie odpowiada. Zobacz logi (docker compose logs worker).' >&2; exit 1
  fi
  [ $((el % 30)) -lt 3 ] && [ "$el" -gt 0 ] && echo "... ${el}s: $line"
  sleep 3
done
