#!/bin/sh
# Prepare private, disk-backed runtime. No network downloads and no Docker builds.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
case "$ROOT" in /home/codexdev/projects/*) ;; *) echo 'Repozytorium musi znajdować się na wolumenie projektów.' >&2; exit 1;; esac
mountpoint -q /home/codexdev/projects || { echo 'Brak wolumenu /home/codexdev/projects.' >&2; exit 1; }
findmnt -T /home/codexdev/projects
project_source=$(findmnt -n -o SOURCE -T /home/codexdev/projects)
root_source=$(findmnt -n -o SOURCE -T /)
[ "$project_source" != "$root_source" ] || { echo 'Wolumen projektów nie jest odrębnym systemem plików.' >&2; exit 1; }
# Fail before large writes when either filesystem lacks its required reserve.
root_kb=$(df -Pk / | awk 'NR==2 {print $4}')
project_kb=$(df -Pk /home/codexdev/projects | awk 'NR==2 {print $4}')
[ "$root_kb" -ge 5242880 ] && [ "$project_kb" -ge 10485760 ] || { echo 'Za mało wolnego miejsca na wolumenach.' >&2; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo 'Wymagany Linux x86_64.' >&2; exit 1; }
[ "$(uname -s)" = Linux ] || { echo 'Wymagany Linux.' >&2; exit 1; }
RUNTIME="$ROOT/.runtime/demo"
WHEELS=${WHEELHOUSE:-"$ROOT/.runtime/build/wheels"}
PYTHON=${PREPARE_PYTHON:-"$ROOT/.runtime/venv/bin/python"}
[ -x "$PYTHON" ] || PYTHON=python3
command -v ffmpeg >/dev/null || { echo 'Zainstaluj systemowy ffmpeg na hoście.' >&2; exit 1; }
[ -d "$WHEELS" ] || { echo "Brak offline wheelhouse: $WHEELS" >&2; exit 1; }
[ -f "$ROOT/api/requirements.lock" ] || { echo 'Brak api/requirements.lock w zintegrowanym repozytorium.' >&2; exit 1; }
umask 077
mkdir -p "$RUNTIME/deps" "$RUNTIME/ffmpeg/bin" "$RUNTIME/ffmpeg/lib" "$RUNTIME/state" "$RUNTIME/tmp" "$RUNTIME/cache"
chmod 700 "$RUNTIME" "$RUNTIME/state"
# Installer and its cache are scoped to the project volume. The wheelhouse is read-only input.
TMPDIR="$RUNTIME/tmp" XDG_CACHE_HOME="$RUNTIME/cache" PIP_CACHE_DIR="$RUNTIME/cache" "$PYTHON" -m pip install --no-index --no-deps --find-links "$WHEELS" --target "$RUNTIME/deps" --upgrade -r "$ROOT/api/requirements.lock"
ff=$(command -v ffmpeg)
ldd "$ff" > "$RUNTIME/ffmpeg/ldd.txt"
if grep -q 'not found' "$RUNTIME/ffmpeg/ldd.txt"; then echo 'Niekompletne zależności systemowego ffmpeg.' >&2; exit 1; fi
cp -L "$ff" "$RUNTIME/ffmpeg/bin/ffmpeg.real"
# ldd provides the transitive ELF dependencies. Copy by SONAME so loader can resolve them.
awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}' "$RUNTIME/ffmpeg/ldd.txt" | while read -r name path; do cp -L "$path" "$RUNTIME/ffmpeg/lib/$name"; done
loader=$(ldd "$ff" | awk '/ld-linux/ {for(i=1;i<=NF;i++) if($i ~ /^\//) {print $i; exit}}')
[ -n "$loader" ] && cp -L "$loader" "$RUNTIME/ffmpeg/lib/ld-linux.so"
cat > "$RUNTIME/ffmpeg/bin/ffmpeg" <<'WRAPPER'
#!/bin/sh
exec /opt/investwatch/ffmpeg/lib/ld-linux.so --library-path /opt/investwatch/ffmpeg/lib /opt/investwatch/ffmpeg/bin/ffmpeg.real "$@"
WRAPPER
chmod 755 "$RUNTIME/ffmpeg/bin/ffmpeg"
"$RUNTIME/ffmpeg/lib/ld-linux.so" --library-path "$RUNTIME/ffmpeg/lib" "$RUNTIME/ffmpeg/bin/ffmpeg.real" -version >/dev/null
printf 'INVESTWATCH_UID=%s\nINVESTWATCH_GID=%s\n' "$(id -u)" "$(id -g)" > "$RUNTIME/compose.env"
chmod 600 "$RUNTIME/compose.env"
echo 'Gotowe. Uruchom: sh ops/demo/start.sh'
