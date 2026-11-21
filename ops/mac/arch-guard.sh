#!/bin/sh
# Kontrola architektury natywnych bibliotek (.so/.dylib) montowanych do kontenera.
# Uzycie: sh ops/mac/arch-guard.sh x86_64|aarch64 SCIEZKA...
# Przerywa (kod 1), gdy znajdzie Mach-O albo ELF innej architektury. Nieistniejace sciezki pomija.
# POSIX sh; do odczytu naglowka uzywa od (BSD i GNU), bez `file`.
set -u
want=${1:-}
case "$want" in
  x86_64) machine=3e00 ;;
  aarch64|arm64) want=aarch64; machine=b700 ;;
  *) echo "Uzycie: arch-guard.sh x86_64|aarch64 SCIEZKA..." >&2; exit 2 ;;
esac
shift
tmp=$(mktemp "${TMPDIR:-/tmp}/archguard.XXXXXX") || exit 2
trap 'rm -f "$tmp"' EXIT INT TERM
for dir in "$@"; do
  [ -e "$dir" ] || continue
  find "$dir" -type f \( -name '*.so' -o -name '*.so.*' -o -name '*.dylib' \) 2>/dev/null |
  while IFS= read -r f; do
    head=$(od -An -tx1 -N20 "$f" 2>/dev/null | tr -d ' \n')
    case "$head" in
      7f454c46*) m=$(printf '%s' "$head" | cut -c37-40)
                 [ "$m" = "$machine" ] || printf '%s (ELF, e_machine=0x%s)\n' "$f" "$m" ;;
      cffaedfe*|cefaedfe*|feedface*|feedfacf*|cafebabe*|bebafeca*) printf '%s (Mach-O)\n' "$f" ;;
    esac
  done >> "$tmp"
done
if [ -s "$tmp" ]; then
  echo "BLAD: natywne biblioteki maja architekture niezgodna z kontenerem linux/$want:" >&2
  head -10 "$tmp" >&2
  echo "Usun katalog z bledna zawartoscia (np. .runtime/demo/deps) i uruchom ponownie sh ops/demo/bootstrap.sh." >&2
  echo "Na macOS kola i biblioteki musza byc budowane w kontenerze linux/arm64, nie na hoscie." >&2
  exit 1
fi
