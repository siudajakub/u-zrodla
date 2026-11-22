#!/bin/sh
# Wspólne funkcje start.sh, start-local.sh i pack-media.sh (wczytywane przez `.`). POSIX sh, BSD userland.
EVENT=2026-11-21
ROOT=${ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)}
ARCHIVE_NAME=replay-media-$EVENT.tar.gz

iw_load_env() { # wczytuje .env (jeśli jest) bez nadpisywania zmiennych już ustawionych w powłoce
  [ -f "$ROOT/.env" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; *=*) ;; *) continue ;; esac
    k=${line%%=*}; v=${line#*=}
    case "$k" in *[!A-Za-z0-9_]*|'') continue ;; esac
    v=${v#\"}; v=${v%\"}; v=${v#\'}; v=${v%\'}
    eval "[ -n \"\${$k+x}\" ]" || { eval "$k=\$v"; export "$k"; }
  done < "$ROOT/.env"
}

iw_sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }

iw_ollama_model_ready() {
  model_ref=$2
  case "${model_ref##*/}" in *:*) ;; *) model_ref="$model_ref:latest" ;; esac
  case "$model_ref" in
    *.*/*|*:*/*) manifest=$model_ref ;;
    */*) manifest="registry.ollama.ai/$model_ref" ;;
    *) manifest="registry.ollama.ai/library/$model_ref" ;;
  esac
  model_tag=${manifest##*:}
  [ -f "$1/models/manifests/${manifest%:*}/$model_tag" ]
}

iw_python() { # Python 3.12 (venv/Homebrew/PATH); wynik w PY312, pierwszy dowolny python3 w PY3
  PY312=
  for c in python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    if "$p" -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)' 2>/dev/null; then PY312=$p; break; fi
  done
  PY3=${PY312:-$(command -v python3 2>/dev/null || true)}
  [ -n "$PY3" ] || { echo 'Brak python3 w PATH. macOS: brew install python@3.12' >&2; return 1; }
}

iw_pack_dir() { printf '%s' "${INVESTWATCH_REPLAY_MEDIA:-$ROOT/.runtime/replay-media/$EVENT}"; }

iw_pack_verify() { # 0 = paczka kompletna i zgodna z manifestem z repozytorium
  (cd "$ROOT" && "$PY3" -m api.replay_pack verify --pack "${1:-$(iw_pack_dir)}") > "${IW_LOG:-/dev/null}" 2>&1
}

iw_find_archive() {
  for c in "${INVESTWATCH_MEDIA_ARCHIVE:-}" "$ROOT/$ARCHIVE_NAME" "$ROOT/.runtime/dist/$ARCHIVE_NAME" "$HOME/Downloads/$ARCHIVE_NAME" "$HOME/Desktop/$ARCHIVE_NAME"; do
    [ -n "$c" ] && [ -f "$c" ] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

iw_unpack() { # $1 = archiwum; rozpakowuje do katalogu tymczasowego, weryfikuje i dopiero wtedy podmienia paczkę
  arc=$1
  if [ -f "$arc.sha256" ]; then
    want=$(cut -d' ' -f1 "$arc.sha256"); got=$(iw_sha "$arc" | cut -d' ' -f1)
    [ "$want" = "$got" ] || { echo "Suma SHA-256 archiwum nie zgadza się z $arc.sha256. Skopiuj plik ponownie." >&2; return 1; }
  else
    echo "Uwaga: brak $arc.sha256. Integralność rozstrzyga manifest z repozytorium (api.replay_pack verify)." >&2
  fi
  if tar -tzf "$arc" | grep -qE '(^/|(^|/)\.\.(/|$))'; then echo 'Archiwum zawiera niebezpieczne ścieżki.' >&2; return 1; fi
  tmp="$ROOT/.runtime/replay-media.incoming"
  rm -rf "$tmp"; mkdir -p "$tmp"
  tar -xzf "$arc" -C "$tmp" || return 1
  [ -d "$tmp/replay-media/$EVENT" ] || { echo "Archiwum nie zawiera replay-media/$EVENT." >&2; rm -rf "$tmp"; return 1; }
  iw_pack_verify "$tmp/replay-media/$EVENT" || { echo 'Paczka z archiwum nie przeszła weryfikacji manifestu.' >&2; rm -rf "$tmp"; return 1; }
  mkdir -p "$ROOT/.runtime/replay-media"
  rm -rf "$ROOT/.runtime/replay-media/$EVENT"
  mv "$tmp/replay-media/$EVENT" "$ROOT/.runtime/replay-media/$EVENT"
  rm -rf "$tmp"
}

IW_OBJECT_DIRS='uploads m2 media-cache meta-import youtube-raw youtube-cache'
STATE_ARCHIVE_NAME=investwatch-state-$EVENT.tar.gz

iw_state_dirs() { # STATE_DIR (SQL) i OBJECTS_DIR (pliki) wariantu Compose; obiekty domyślnie obok stanu
  STATE_DIR=${INVESTWATCH_STATE_DIR:-$ROOT/.runtime/demo/state}
  OBJECTS_DIR=${INVESTWATCH_OBJECTS_DIR:-$(dirname -- "$STATE_DIR")/objects}
  INVESTWATCH_STATE_DIR=$STATE_DIR; INVESTWATCH_OBJECTS_DIR=$OBJECTS_DIR
  export INVESTWATCH_STATE_DIR INVESTWATCH_OBJECTS_DIR
}

iw_objects_layout() { # $1 = stan (SQL), $2 = obiekty. Przenosi obiekty ze starego układu (wszystko w stanie) i tworzy punkty montowania.
  for d in $IW_OBJECT_DIRS; do
    if [ -d "$1/$d" ] && [ -n "$(ls -A "$1/$d" 2>/dev/null)" ] && [ -z "$(ls -A "$2/$d" 2>/dev/null)" ]; then
      mkdir -p "$2"; rm -rf "$2/$d"; mv "$1/$d" "$2/$d"; echo "Przeniesiono $d do magazynu obiektów ($2)."
    fi
    mkdir -p "$1/$d" "$2/$d"
  done
  chmod 700 "$2"
}

iw_find_state_archive() {
  [ "${INVESTWATCH_STATE_ARCHIVE:-}" != off ] || return 1
  for c in "${INVESTWATCH_STATE_ARCHIVE:-}" "$ROOT/$STATE_ARCHIVE_NAME" "$ROOT/.runtime/dist/$STATE_ARCHIVE_NAME" "$HOME/Downloads/$STATE_ARCHIVE_NAME"; do
    [ -n "$c" ] && [ -f "$c" ] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

iw_restore_state() { # $1 = stan, $2 = obiekty (local: ten sam katalog). 0 = przywrócono gotowy stan; inaczej normalny bootstrap.
  [ ! -f "$1/cases.sqlite3" ] || return 1
  arc=$(iw_find_state_archive) || return 1
  echo "Gotowy stan pokazu: $arc"
  "$PY3" "$ROOT/ops/demo/state_pack.py" restore --archive "$arc" --state "$1" --objects "$2"
}

iw_need_pack() { # gwarantuje paczkę mediów albo kończy z instrukcją (kod 3). INVESTWATCH_ALLOW_NO_MEDIA=1 pomija.
  iw_python || exit 1
  IW_LOG="$ROOT/.runtime/pack-verify.log"; mkdir -p "$ROOT/.runtime"
  if iw_pack_verify; then return 0; fi
  if [ -z "${INVESTWATCH_REPLAY_MEDIA:-}" ] && arc=$(iw_find_archive); then
    echo "Rozpakowuję paczkę mediów z $arc"
    iw_unpack "$arc" && iw_pack_verify && return 0
  fi
  [ "${INVESTWATCH_ALLOW_NO_MEDIA:-0}" != 1 ] || { echo 'Start bez paczki mediów. Transkrypcje i kadry z paczki będą niedostępne.' >&2; return 0; }
  cat >&2 <<MSG
BRAK PACZKI MEDIÓW REPLAY. Paczka zawiera transkrypcje i kadry filmów z pokazu.
Powód: $(tail -n 5 "$IW_LOG" | tr '\n' ' ' | cut -c1-300)
Na maszynie, która ma paczkę (devbox):  sh ops/demo/pack-media.sh
Skopiuj OBA pliki do katalogu projektu na tym komputerze (poza Git):
  $ARCHIVE_NAME   i   $ARCHIVE_NAME.sha256
i uruchom to polecenie ponownie. Własna lokalizacja: INVESTWATCH_MEDIA_ARCHIVE=/sciezka/do/archiwum.tar.gz
Start bez tych mediów: INVESTWATCH_ALLOW_NO_MEDIA=1
MSG
  exit 3
}
