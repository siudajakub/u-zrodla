#!/bin/sh
# The user service starts this file in the project checkout.
set -eu
umask 077
state=.runtime/watch
mkdir -p "$state/reports"
result=0
/usr/bin/python3 tools/watch_sources.py run --keep-text --db "$state/watch.sqlite3" || result=$?
day=$(TZ=Europe/Warsaw date +%F)
report=$(mktemp "$state/reports/.$day.XXXXXX")
trap 'rm -f "$report"' EXIT
/usr/bin/python3 tools/watch_sources.py report --date "$day" --timezone Europe/Warsaw --db "$state/watch.sqlite3" > "$report"
mv "$report" "$state/reports/$day.json"
exit "$result"
