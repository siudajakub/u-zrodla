#!/bin/sh
# Build the optional Astryx desk using dependencies pinned in web/package-lock.json.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
cd "$ROOT"
case "${1:---offline}" in
  --offline) npm_mode=--offline ;;
  --prepare) npm_mode=--prefer-offline ;;
  *) echo "Użycie: sh ops/demo/prepare-preview.sh [--offline|--prepare]" >&2; exit 2 ;;
esac

if [ -d /home/codexdev/projects/.vps-runtime ]; then
  mountpoint -q /home/codexdev/projects
  case "$ROOT" in /home/codexdev/projects/*) ;; *) exit 1 ;; esac
fi
runtime="$ROOT/.runtime/desk-preview"
mkdir -p "$runtime/tmp"
exec 9>"$runtime/build.lock"
flock 9

source_hash() {
    {
        printf '%s\n' web/app.js web/build-preview.mjs web/package.json web/package-lock.json
        find web/src -type f
    } | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -d' ' -f1
}
output=web/theme-preview
complete() {
    [ -s "$output/index.html" ] && [ -s "$output/preview.js" ] &&
        [ -s "$output/preview.css" ] && [ -s "$output/fonts/figtree.LICENSE.txt" ] &&
        [ "$(find "$output/fonts" -name '*.woff2' -type f | wc -l)" -eq 8 ]
}
fingerprint=$(source_hash)
if complete && [ "$(cat "$output/.source-sha256" 2>/dev/null || true)" = "$fingerprint" ]; then
    exit 0
fi

node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 13)) process.exit(1)' ||
    { echo "Podgląd Astryx wymaga Node.js od 22.13." >&2; exit 1; }
if [ -d /home/codexdev/projects/.vps-runtime ]; then
  [ "$(df -Pk "$ROOT" | awk 'NR==2{print $4}')" -ge 10485760 ]
  [ "$(df -Pk / | awk 'NR==2{print $4}')" -ge 5242880 ]
fi
export TMPDIR="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
lock_hash=$(sha256sum web/package-lock.json | cut -d' ' -f1)
if [ ! -x web/node_modules/.bin/esbuild ] ||
   [ "$(cat web/node_modules/.investwatch-lock-sha256 2>/dev/null || true)" != "$lock_hash" ]; then
    npm --prefix web ci "$npm_mode" --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=15000 \
        --cache "${INVESTWATCH_PREVIEW_NPM_CACHE:-$runtime/npm}"
    printf '%s\n' "$lock_hash" > web/node_modules/.investwatch-lock-sha256
fi
npm --prefix web run build
complete
[ "$(source_hash)" = "$fingerprint" ]
printf '%s\n' "$fingerprint" > "$output/.source-sha256"
