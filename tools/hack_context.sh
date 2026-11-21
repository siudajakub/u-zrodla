#!/bin/sh
# Load project context for Codex and Claude Code. Hook failures do not block startup.

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd) || exit 0
session=""
if [ "${1:-}" = "--claude" ]; then
    session=$(python3 "$root/tools/session_log.py" id --claude-hook)
    shift
fi

if [ "${1:-}" = "--remind" ]; then
    printf '%s\n' "Zachowaj w podsumowaniu cel, decyzję, wynik próby, następny krok i ID sesji."
    printf '%s\n' "Po wznowieniu uzupełnij log projektu i rekord swojej linii, jeśli stan się zmienił."
    if [ -n "$session" ]; then
        python3 "$root/tools/session_log.py" latest --session "$session" --limit 1
    fi
    exit 0
fi

if [ -n "$session" ]; then
    printf 'ID sesji Claude Code: %s\n' "$session"
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
        printf "export INVESTWATCH_SESSION_ID='%s'\n" "$session" >> "$CLAUDE_ENV_FILE"
    fi
fi

printf '%s\n' "Linie i zakresy prac"
python3 "$root/tools/hack_status.py" 2>&1 || printf '%s\n' "Odczytaj TEAM_BOARD.md i docs/lanes."
printf '\n%s\n' "Ostatnie wpisy sesji projektu"
python3 "$root/tools/session_log.py" latest

exit 0
