#!/bin/sh
# Odbior stanowiska macOS (Apple Silicon): diagnostyka tylko do odczytu + opcjonalny pomiar.
# Zgodny z POSIX sh i BSD userland (bez GNU sed/stat/date, bez jq, bez flock).
# Zapisuje jedyny plik: raport JSON (domyslnie .runtime/mac/check-<UTC>.json).
# Raport nie zawiera nazwy uzytkownika, nazwy hosta, adresow IP ani sciezek domowych.
#
#   sh ops/mac/check.sh                      sama diagnostyka
#   sh ops/mac/check.sh --measure            + pomiar jednej oceny (zimny/cieply)
#   sh ops/mac/check.sh --measure --expect-offline   odmawia pomiaru, gdy siec dziala
# Opcje: --runs N (domyslnie 3) --model NAZWA --fixture PLIK --capture-id ID --out PLIK
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P) || exit 2
cd "$ROOT" || exit 2

MEASURE=0
EXPECT_OFFLINE=0
RUNS=3
MODEL=qwen3.5:9b
FIXTURE=fixtures/raw/discovery/2026-11-21.json
CAPTURE_ID=youtube:xtMqKkFO-0M
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=".runtime/mac/check-$STAMP.json"
OLLAMA=http://127.0.0.1:11434

while [ $# -gt 0 ]; do
  case "$1" in
    --measure) MEASURE=1 ;;
    --expect-offline) EXPECT_OFFLINE=1 ;;
    --runs) shift; RUNS=${1:-}; ;;
    --model) shift; MODEL=${1:-} ;;
    --fixture) shift; FIXTURE=${1:-} ;;
    --capture-id) shift; CAPTURE_ID=${1:-} ;;
    --out) shift; OUT=${1:-} ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Nieznana opcja: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$RUNS" in ''|*[!0-9]*|0) echo "--runs wymaga liczby > 0" >&2; exit 2 ;; esac
[ -n "$MODEL" ] && [ -n "$OUT" ] || { echo "Puste --model lub --out" >&2; exit 2; }

T=$(mktemp -d "${TMPDIR:-/tmp}/iwmac.XXXXXX") || exit 2
trap 'rm -rf "$T"; [ -z "${SAMPLER:-}" ] || kill "$SAMPLER" 2>/dev/null' EXIT INT TERM
: > "$T/blockers"; : > "$T/warnings"

# ---------- pomocnicze: budowa JSON bez jq ----------
js_esc() { printf '%s' "$1" | tr '\n\r\t' '   ' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | cut -c1-400; }
kvs() { if [ -z "$3" ]; then printf '"%s": null\n' "$2" >> "$1"; else printf '"%s": "%s"\n' "$2" "$(js_esc "$3")" >> "$1"; fi; }
kvn() { case "$3" in ''|*[!0-9.]*) printf '"%s": null\n' "$2" >> "$1" ;; *) printf '"%s": %s\n' "$2" "$3" >> "$1" ;; esac; }
kvb() { printf '"%s": %s\n' "$2" "$3" >> "$1"; }
kvr() { printf '"%s": %s\n' "$2" "$3" >> "$1"; }
wrap() { printf '{'; [ -s "$1" ] && sed '$!s/$/,/' "$1"; printf '}'; }
blocker() { printf '%s\n' "$1" >> "$T/blockers"; echo "BLOKADA: $1"; }
warning() { printf '%s\n' "$1" >> "$T/warnings"; echo "UWAGA:   $1"; }
note() { echo "         $1"; }
have() { command -v "$1" >/dev/null 2>&1; }
arr() { # plik z liniami -> tablica JSON
  printf '['; [ -s "$1" ] && while IFS= read -r line; do printf '"%s",' "$(js_esc "$line")"; done < "$1" | sed 's/,$//'; printf ']'; }
ver_ge() { # ver_ge "3.12.3" 3 12
  set -- "$(printf '%s' "$1" | sed -n 's/^[^0-9]*\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p')" "$2" "$3"
  [ -n "$1" ] || return 1
  set -- $1 "$2" "$3"
  [ "$1" -gt "$3" ] || { [ "$1" -eq "$3" ] && [ "$2" -ge "$4" ]; }
}
gib() { awk -v b="$1" 'BEGIN{printf "%.1f", b/1073741824}'; }
arch_of() { # klasyfikacja pliku binarnego przez `file`
  out=$(file -b "$1" 2>/dev/null || true)
  case "$out" in
    *ELF*"ARM aarch64"*|*ELF*aarch64*) echo elf-aarch64 ;;
    *ELF*x86-64*) echo elf-x86_64 ;;
    *Mach-O*arm64*) echo macho-arm64 ;;
    *Mach-O*x86_64*) echo macho-x86_64 ;;
    '') echo unknown ;;
    *) echo other ;;
  esac
}
pyok() { have python3 && { [ "$(uname -s)" != Darwin ] || [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; }

echo "== InvestWatch / odbior macOS ($STAMP) =="

# ---------- 1. system ----------
S="$T/system"; : > "$S"
OS=$(uname -s); ARCH=$(uname -m)
kvs "$S" os "$OS"; kvs "$S" machine "$ARCH"
if [ "$OS" != Darwin ]; then
  warning "To nie macOS (uname -s = $OS). Wynik nie dotyczy Maca; skrypt jest przeznaczony na Apple Silicon."
fi
kvs "$S" macosVersion "$(sw_vers -productVersion 2>/dev/null || true)"
kvs "$S" cpu "$(sysctl -n machdep.cpu.brand_string 2>/dev/null || true)"
kvs "$S" hardwareModel "$(sysctl -n hw.model 2>/dev/null || true)"
kvn "$S" cpuCores "$(sysctl -n hw.ncpu 2>/dev/null || true)"
TRANSLATED=$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)
kvb "$S" underRosetta "$([ "$TRANSLATED" = 1 ] && echo true || echo false)"
if [ "$OS" = Darwin ] && [ "$ARCH" != arm64 ]; then
  blocker "Architektura powloki: $ARCH (oczekiwano arm64). Terminal pod Rosetta lub Mac z Intelem."
fi
[ "$TRANSLATED" = 1 ] && blocker "Powloka dziala pod Rosetta (proc_translated=1): Python/Node/Ollama beda x86_64."
MEMB=$(sysctl -n hw.memsize 2>/dev/null || true)
kvn "$S" unifiedMemoryBytes "$MEMB"
if [ -n "$MEMB" ]; then
  MEMG=$(gib "$MEMB"); kvn "$S" unifiedMemoryGiB "$MEMG"
  echo "Pamiec zunifikowana: $MEMG GiB"
  if [ "$MEMB" -lt 8589934592 ]; then blocker "Pamiec $MEMG GiB: za malo na qwen3.5:9b (wagi ok. 6-7 GB). Uzyj mniejszego modelu (patrz README, sciezka awaryjna)."
  elif [ "$MEMB" -lt 17179869184 ]; then warning "Pamiec $MEMG GiB (< 16): 9B + Docker + przegladarka moze wchodzic w swap. Zmierz --measure i obserwuj swap."; fi
fi
kvs "$S" gpuWiredLimitMb "$(sysctl -n iogpu.wired_limit_mb 2>/dev/null || true)"
kvs "$S" swapUsage "$(sysctl -n vm.swapusage 2>/dev/null || true)"
DFK=$(df -Pk . 2>/dev/null | awk 'NR==2{print $4}')
kvn "$S" freeDiskKiB "$DFK"
if [ -n "$DFK" ]; then
  FREEG=$(awk -v k="$DFK" 'BEGIN{printf "%.1f", k/1048576}'); kvn "$S" freeDiskGiB "$FREEG"
  echo "Wolne miejsce (wolumen projektu): $FREEG GiB"
  [ "$DFK" -lt 15728640 ] && blocker "Wolne miejsce $FREEG GiB (< 15): obraz Pythona, model Qwen ok. 6,6 GB, Vosk, E5 i node_modules."
fi
echo "System: $OS $ARCH, macOS $(sw_vers -productVersion 2>/dev/null || echo '?'), $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo '?')"

# ---------- 2. narzedzia ----------
TL="$T/tools"; : > "$TL"
if pyok; then
  PYV=$(python3 -c 'import platform;print(platform.python_version())' 2>/dev/null || true)
  kvs "$TL" python3 "$PYV"; echo "Python: $PYV"
  ver_ge "$PYV" 3 12 || blocker "Python $PYV < 3.12 (bootstrap.sh:13 wymaga 3.12; analysis.* korzysta z 3.11+). Zainstaluj python@3.12."
else kvs "$TL" python3 ""; blocker "Brak dzialajacego python3 (3.12)."; fi
if have node; then NV=$(node --version 2>/dev/null | sed 's/^v//'); kvs "$TL" node "$NV"; echo "Node: $NV"
  ver_ge "$NV" 22 13 || warning "Node $NV < 22.13 (prepare-preview.sh:38): podglad Astryx sie nie zbuduje."
else kvs "$TL" node ""; warning "Brak Node (tylko podglad Astryx /theme-preview/ go wymaga)."; fi
have npm && kvs "$TL" npm "$(npm --version 2>/dev/null || true)" || kvs "$TL" npm ""
if have ffmpeg; then FV=$(ffmpeg -version 2>/dev/null | sed -n '1s/^ffmpeg version \([^ ]*\).*/\1/p'); kvs "$TL" ffmpeg "$FV"; echo "FFmpeg (host): $FV"
  kvs "$TL" ffmpegBinary "$(arch_of "$(command -v ffmpeg)")"
else kvs "$TL" ffmpeg ""; warning "Brak ffmpeg na hoscie (host-owy nie jest uzywany przez kontenery; patrz README, blokady B2)."; fi
for c in curl file git; do have "$c" || warning "Brak polecenia $c."; done
have shasum && kvb "$TL" shasum true || kvb "$TL" shasum false
have sha256sum && kvb "$TL" gnuSha256sum true || { kvb "$TL" gnuSha256sum false; note "brak sha256sum/flock (GNU) - ops/demo/prepare-preview.sh:19,25,45 nie zadziala bez poprawki"; }
have flock && kvb "$TL" gnuFlock true || kvb "$TL" gnuFlock false
kvs "$TL" gitHead "$(git rev-parse --short HEAD 2>/dev/null || true)"

# ---------- 3. Docker ----------
D="$T/docker"; : > "$D"
DOCKER_OK=0; IMAGE_OK=0
if have docker; then
  kvs "$D" client "$(docker --version 2>/dev/null | sed 's/^Docker version \([^,]*\),.*/\1/')"
  kvs "$D" compose "$(docker compose version --short 2>/dev/null || true)"
  if docker info >/dev/null 2>&1; then
    DOCKER_OK=1
    DOS=$(docker info --format '{{.OSType}}' 2>/dev/null); DAR=$(docker info --format '{{.Architecture}}' 2>/dev/null)
    DMEM=$(docker info --format '{{.MemTotal}}' 2>/dev/null); DCPU=$(docker info --format '{{.NCPU}}' 2>/dev/null)
    kvs "$D" serverOs "$DOS"; kvs "$D" serverArchitecture "$DAR"; kvn "$D" vmMemoryBytes "$DMEM"; kvn "$D" vmCpus "$DCPU"
    kvs "$D" serverVersion "$(docker info --format '{{.ServerVersion}}' 2>/dev/null)"
    echo "Docker: $DOS/$DAR, pamiec VM $(gib "${DMEM:-0}") GiB, CPU $DCPU"
    case "$DAR" in aarch64|arm64) ;; *) blocker "Serwer Docker: $DAR (oczekiwano aarch64). Kontenery x86_64 pod emulacja nie uzyskaja natywnej libvosk ani kol aarch64." ;; esac
    [ -n "$DMEM" ] && [ "$DMEM" -lt 3221225472 ] && warning "VM Docker ma $(gib "$DMEM") GiB (< 3): dwa serwisy po 1200 MiB (compose.yaml:24) + narzut. Zwieksz w Docker Desktop > Settings > Resources."
    IA=$(docker image inspect python:3.12-bookworm --format '{{.Os}}/{{.Architecture}}' 2>/dev/null || true)
    kvs "$D" baseImage "${IA:-absent}"
    if [ -z "$IA" ]; then warning "Brak lokalnego python:3.12-bookworm (compose.yaml:17 + pull_policy: never). Jednorazowo: docker pull --platform linux/arm64 python:3.12-bookworm"
    elif [ "$IA" != linux/arm64 ]; then blocker "Obraz python:3.12-bookworm ma platforme $IA (potrzebne linux/arm64)."
    else IMAGE_OK=1; fi
  else kvs "$D" serverOs ""; blocker "Docker zainstalowany, ale demon nie odpowiada (uruchom Docker Desktop / OrbStack)."; fi
else kvs "$D" client ""; blocker "Brak docker (potrzebny Docker Compose dla pelnego demo)."; fi

# ---------- 4. artefakty .runtime (architektura natywnych bibliotek) ----------
A="$T/artifacts"; : > "$A"
check_bin() { # klucz sciezka
  if [ -n "$2" ] && [ -f "$2" ]; then
    k=$(arch_of "$2"); kvs "$A" "$1" "$k"; kvs "$A" "$1Raw" "$(file -b "$2" 2>/dev/null)"
    echo "$1: $k"
    case "$k" in
      elf-aarch64) ;;
      *) blocker "$1 = $k. Kontenery linux/arm64 laduja tylko ELF aarch64 (analysis/transcribe.py:49, compose.yaml:10-13 montuje .runtime)." ;;
    esac
  else kvs "$A" "$1" absent; echo "$1: brak (jeszcze nie przygotowano)"; fi
}
check_bin libvosk ".runtime/asr/vosk/libvosk.so"
check_bin ffmpegReal ".runtime/demo/ffmpeg/bin/ffmpeg.real"
check_bin pydanticCore "$(find .runtime/demo/deps/pydantic_core -maxdepth 1 -name '*.so' 2>/dev/null | head -1)"
check_bin onnxruntime "$(find .runtime/semantic/deps/onnxruntime/capi -maxdepth 1 -name 'onnxruntime_pybind11_state*.so' 2>/dev/null | head -1)"
kvb "$A" asrModelPresent "$([ -f .runtime/asr/vosk-model-small-pl-0.22/am/final.mdl ] && echo true || echo false)"
kvb "$A" semanticWeightsPresent "$([ -f .runtime/semantic/model_quantized.onnx ] && echo true || echo false)"
kvb "$A" composeEnvPresent "$([ -f .runtime/demo/compose.env ] && echo true || echo false)"

# ---------- 4b. paczka mediow replay i kolejka "Co wymaga sprawdzenia" ----------
PACK=${INVESTWATCH_REPLAY_MEDIA:-.runtime/replay-media/2026-11-21}
if pyok; then
  if python3 -m api.replay_pack verify --pack "$PACK" >"$T/pack.out" 2>&1; then PK=present; else PK=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["state"])' "$T/pack.out" 2>/dev/null || echo unreadable); fi
else
  if [ -f "$PACK/MANIFEST.json" ]; then PK=present-unverified; else PK=missing; fi
fi
kvs "$A" replayMediaPack "$PK"; echo "paczka mediow replay: $PK ($PACK)"
[ "$PK" = present ] || [ "$PK" = present-unverified ] || blocker "Paczka mediow replay: $PK. Kolejka review bedzie pusta. Skopiuj replay-media-2026-11-21.tar.gz(+.sha256) do katalogu projektu i uruchom sh ops/demo/start.sh (ops/demo/pack-media.sh tworzy archiwum)."
PORT=${INVESTWATCH_PORT:-8769}
if pyok && python3 ops/demo/queue_status.py --port "$PORT" --expect-count 4 >"$T/queue.out" 2>&1; then QS=ok; else QS=$(cut -c1-300 "$T/queue.out" 2>/dev/null); fi
if pyok && have curl && curl -sS -m 4 -o /dev/null "http://127.0.0.1:$PORT/v1/health" 2>/dev/null; then
  kvb "$A" apiUp true; kvs "$A" reviewQueue "$(cat "$T/queue.out")"; echo "kolejka review: $(cat "$T/queue.out")"
  [ "$QS" = ok ] || warning "Kolejka review (GET /v1/queues/review) nie ma 4 znanych filmow lub skany trwaja. Kroki: sh ops/demo/start.sh --reset."
else
  kvb "$A" apiUp false; kvs "$A" reviewQueue ""; echo "API na porcie $PORT: nie odpowiada (jeszcze nie uruchomione?)"
fi

# ---------- 5. siec ----------
N="$T/network"; : > "$N"
if have curl && curl -sS -m 4 -o /dev/null -I https://huggingface.co >/dev/null 2>&1; then NET=true; else NET=false; fi
kvb "$N" internetReachable "$NET"; echo "Internet osiagalny: $NET"

# ---------- 6. Ollama ----------
O="$T/ollama"; : > "$O"
OLLAMA_UP=0; MODEL_OK=0
if have ollama; then kvs "$O" cli "$(ollama --version 2>&1 | sed -n 's/.*version is \(.*\)/\1/p' | head -1)"; else kvs "$O" cli ""; warning "Brak polecenia ollama."; fi
APIV=$(curl -sS -m 3 "$OLLAMA/api/version" 2>/dev/null | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p')
if [ -n "$APIV" ]; then
  OLLAMA_UP=1; kvs "$O" serverVersion "$APIV"; kvb "$O" serverUp true; echo "Ollama: serwer $APIV na 127.0.0.1:11434"
  curl -sS -m 5 "$OLLAMA/api/tags" > "$T/tags.json" 2>/dev/null
  if pyok; then
    python3 -c '
import json,sys
want=sys.argv[2]
d=json.load(open(sys.argv[1]))
m=next((x for x in d.get("models",[]) if x.get("name")==want or x.get("model")==want),None)
if not m: print("null"); raise SystemExit
det=m.get("details") or {}
print(json.dumps({"name":m.get("name"),"digest":m.get("digest"),"sizeBytes":m.get("size"),
 "quantization":det.get("quantization_level"),"parameterSize":det.get("parameter_size"),
 "family":det.get("family"),"format":det.get("format"),"modifiedAt":m.get("modified_at")}))' "$T/tags.json" "$MODEL" > "$T/model.json" 2>/dev/null || echo null > "$T/model.json"
  else echo null > "$T/model.json"; fi
  kvr "$O" model "$(cat "$T/model.json")"
  if [ "$(cat "$T/model.json")" = null ]; then
    blocker "Ollama nie ma modelu $MODEL (ollama pull $MODEL)."
  else
    MODEL_OK=1
    echo "Model $MODEL:"; ollama list 2>/dev/null | awk -v m="$MODEL" 'NR==1 || $1==m' | sed 's/^/         /'
    cat "$T/model.json" | sed 's/^/         /'
  fi
  PSF=$(curl -sS -m 3 "$OLLAMA/api/ps" 2>/dev/null); kvn "$O" loadedNow "$(printf '%s' "$PSF" | grep -c '"name"')"
else
  kvb "$O" serverUp false; kvr "$O" model null
  blocker "Ollama nie odpowiada na 127.0.0.1:11434 (uruchom aplikacje Ollama lub: ollama serve)."
fi

# ---------- 7. kontener -> Ollama na hoscie ----------
C="skipped"
if [ "$DOCKER_OK" = 1 ] && [ "$IMAGE_OK" = 1 ] && [ "$OLLAMA_UP" = 1 ]; then
  R=$(docker run --rm --pull never --platform linux/arm64 python:3.12-bookworm python -c '
import urllib.request as u
try: print(u.urlopen("http://host.docker.internal:11434/api/version",timeout=5).status)
except Exception as e: print("ERR "+type(e).__name__)' 2>/dev/null | tail -1)
  case "$R" in 200) C=ok ;; *) C="unreachable ${R:-no-output}"
    warning "Kontener nie laczy sie z Ollama przez host.docker.internal:11434 ($R). Dotyczy dopiero integracji workera; analysis/ollama_review.py dziala na hoscie i uzywa 127.0.0.1." ;; esac
fi
echo "Kontener -> Ollama (host.docker.internal): $C"

# ---------- 8. pomiar ----------
MEAS="null"
run_measure() {
  [ "$OLLAMA_UP" = 1 ] && [ "$MODEL_OK" = 1 ] || { MEAS='{"skipped":"Ollama lub model niedostepne"}'; return; }
  pyok && ver_ge "$PYV" 3 12 || { MEAS='{"skipped":"brak Pythona 3.12"}'; return; }
  [ -f "$FIXTURE" ] || { MEAS='{"skipped":"brak pliku fixture"}'; return; }
  if [ "$EXPECT_OFFLINE" = 1 ] && [ "$NET" = true ]; then
    blocker "--expect-offline: siec dziala. Wylacz Wi-Fi/Ethernet i uruchom ponownie; pomiar odrzucony."
    MEAS='{"skipped":"siec dostepna mimo --expect-offline"}'; return
  fi
  export PYTHONDONTWRITEBYTECODE=1
  PROMPT_CHARS=$(python3 -c '
import sys
from pathlib import Path
from analysis.openrouter_review import load_capture, capture_fragments, review_messages
c=load_capture(Path(sys.argv[1]),sys.argv[2])
print(sum(len(str(m.get("content",""))) for m in review_messages(c["module"],capture_fragments(c))))' "$FIXTURE" "$CAPTURE_ID" 2>/dev/null)
  echo "Pomiar: $MODEL, $RUNS x zimny + $RUNS x cieply, prompt $PROMPT_CHARS znakow, siec=$NET"
  : > "$T/runs"; n=0
  for phase in cold warm; do
    i=0
    while [ "$i" -lt "$RUNS" ]; do
      i=$((i+1)); n=$((n+1))
      if [ "$phase" = cold ]; then
        curl -sS -m 10 -d "{\"model\":\"$MODEL\",\"keep_alive\":0}" "$OLLAMA/api/generate" >/dev/null 2>&1
        w=0; while [ "$w" -lt 20 ] && ! curl -sS -m 3 "$OLLAMA/api/ps" 2>/dev/null | grep -Eq '"models": *\[\]'; do sleep 1; w=$((w+1)); done
      fi
      SWAP0=$(sysctl -n vm.swapusage 2>/dev/null || true)
      : > "$T/samples"
      ( while :; do
          r=$(ps -axo rss=,comm= 2>/dev/null | awk '/[Oo]llama/ {s+=$1} END{print s+0}')
          f=$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: *\([0-9]*\)%.*/\1/p' | head -1)
          printf '%s %s\n' "$r" "${f:-}" >> "$T/samples"; sleep 1
        done ) &
      SAMPLER=$!
      if [ "$MODEL" = qwen3.5:9b ]; then
        /usr/bin/time -l python3 -m analysis.ollama_review "$FIXTURE" --capture-id "$CAPTURE_ID" > "$T/out.txt" 2> "$T/time.txt"; RC=$?
      else # inny model: tylko podmiana stalej MODEL w pamieci, bez zmiany plikow repo
        /usr/bin/time -l python3 -c '
import sys, analysis.ollama_review as m
m.MODEL=sys.argv[1]; raise SystemExit(m.main(sys.argv[2:]))' "$MODEL" "$FIXTURE" --capture-id "$CAPTURE_ID" > "$T/out.txt" 2> "$T/time.txt"; RC=$?
      fi
      kill "$SAMPLER" 2>/dev/null; wait "$SAMPLER" 2>/dev/null; SAMPLER=
      SWAP1=$(sysctl -n vm.swapusage 2>/dev/null || true)
      WALL=$(awk '/ real /{print $1; exit}' "$T/time.txt")
      PYRSS=$(awk '/maximum resident set size/{print $1; exit}' "$T/time.txt")
      OLRSS=$(awk '$1+0>m{m=$1+0} END{print m*1024+0}' "$T/samples")
      MINFREE=$(awk 'NF>=2 && $2!="" {if(min==""||$2<min)min=$2} END{print min}' "$T/samples")
      curl -sS -m 3 "$OLLAMA/api/ps" > "$T/ps.json" 2>/dev/null
      PSJ=$(python3 -c '
import json,sys
try:
    m=(json.load(open(sys.argv[1])).get("models") or [None])[0] or {}
except Exception: m={}
print(json.dumps({k:m.get(k) for k in ("size","size_vram","context_length","digest")}))' "$T/ps.json" 2>/dev/null || echo null)
      REV=$(python3 -c '
import json,sys,hashlib
try:
    d=json.loads(open(sys.argv[1]).read().strip().splitlines()[-1])
except Exception:
    print(json.dumps({"parsed":False})); raise SystemExit
print(json.dumps({"parsed":True,"status":d.get("status"),"signal":d.get("signal"),
 "errorCode":(d.get("error") or {}).get("code"),"reportedModel":d.get("reportedModel"),
 "hasEvidence":bool(d.get("evidence")),
 "outputSha256":hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()}))' "$T/out.txt" 2>/dev/null || echo '{"parsed":false}')
      printf '{"n":%s,"phase":"%s","exitCode":%s,"wallSeconds":%s,"pythonPeakRssBytes":%s,"ollamaPeakRssBytesSampled":%s,"minFreeMemoryPercentSampled":%s,"swapBefore":"%s","swapAfter":"%s","ollamaPs":%s,"review":%s}\n' \
        "$n" "$phase" "$RC" "${WALL:-null}" "${PYRSS:-null}" "${OLRSS:-null}" "${MINFREE:-null}" "$(js_esc "$SWAP0")" "$(js_esc "$SWAP1")" "${PSJ:-null}" "$REV" >> "$T/runs"
      echo "  $phase #$i: exit=$RC wall=${WALL:-?}s pyRSS=${PYRSS:-?}B minFree=${MINFREE:-?}% $(printf '%s' "$REV" | tr -d '{}"' | cut -c1-120)"
    done
  done
  CTX=$(python3 -c 'import json,sys;print(json.dumps({"promptChars":int(sys.argv[1] or 0)}))' "${PROMPT_CHARS:-0}" 2>/dev/null || echo null)
  MEAS=$(printf '{"model":"%s","fixture":"%s","captureId":"%s","runsPerPhase":%s,"internetReachableDuringMeasure":%s,"context":%s,"runs":[%s]}' \
    "$(js_esc "$MODEL")" "$(js_esc "$FIXTURE")" "$(js_esc "$CAPTURE_ID")" "$RUNS" "$NET" "$CTX" "$(sed '$!s/$/,/' "$T/runs" | tr -d '\n')")
}
[ "$MEASURE" = 1 ] && run_measure

# ---------- 9. raport ----------
mkdir -p "$(dirname "$OUT")" || exit 2
NB=$(wc -l < "$T/blockers" | tr -d ' '); NW=$(wc -l < "$T/warnings" | tr -d ' ')
if [ "$NB" -gt 0 ]; then VERDICT=blocked; elif [ "$NW" -gt 0 ]; then VERDICT=warnings; else VERDICT=ready; fi
{
  printf '{"schema":"investwatch-mac-check-1","generatedAtUtc":"%s","verdict":"%s",\n' "$STAMP" "$VERDICT"
  printf '"system":%s,\n"tools":%s,\n"docker":%s,\n"artifacts":%s,\n"network":%s,\n"ollama":%s,\n"containerToOllama":"%s",\n' \
    "$(wrap "$S")" "$(wrap "$TL")" "$(wrap "$D")" "$(wrap "$A")" "$(wrap "$N")" "$(wrap "$O")" "$(js_esc "$C")"
  printf '"measure":%s,\n"blockers":%s,\n"warnings":%s}\n' "$MEAS" "$(arr "$T/blockers")" "$(arr "$T/warnings")"
} > "$OUT"
if pyok; then python3 -c 'import json,sys;json.load(open(sys.argv[1]))' "$OUT" 2>/dev/null || echo "UWAGA: raport JSON nie przeszedl walidacji skladni: $OUT" >&2; fi
echo "== Werdykt: $VERDICT (blokady: $NB, uwagi: $NW). Raport: $OUT =="
[ "$NB" -eq 0 ]
