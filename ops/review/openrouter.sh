#!/bin/sh
# Run one explicit development comparison from any working directory.
# Relative capture paths are resolved against the caller's current directory.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -f "$root/.env.openrouter" ]; then
    # Read a single setting as data, without executing shell expressions: first matching line,
    # optional "export", CR, surrounding spaces and one pair of quotes are removed.
    OPENROUTER_API_KEY=$(sed -n \
        -e 's/\r$//' \
        -e 's/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}OPENROUTER_API_KEY[[:space:]]*=[[:space:]]*//p' \
        "$root/.env.openrouter" | head -n 1 | sed \
        -e 's/[[:space:]]*$//' \
        -e 's/^"\(.*\)"$/\1/' \
        -e "s/^'\(.*\)'\$/\1/")
    export OPENROUTER_API_KEY
fi
PYTHONPATH="$root${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
exec python3 -m analysis.openrouter_review "$@"
