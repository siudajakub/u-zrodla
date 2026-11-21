#!/bin/sh
# Measure the local LLM second opinion (material type) on the agent-labelled held-out set.
# Runs on the Mac host with native Ollama (Metal). Uses only the Python standard library.
#
#   sh ops/mac/measure-llm.sh                         # default model qwen3.5:4b-q4_K_M, held-out split
#   sh ops/mac/measure-llm.sh --model qwen3.5:9b-q4_K_M
#   sh ops/mac/measure-llm.sh --pull --split all      # download the model first (needs Internet once)
#
# Output: .runtime/mac/llm-<model>-<UTC time>.json with accuracy, confusion matrix, share of
# answers rejected by the quote validator, latency and the weights digest. Compare with
# fixtures/labeled/ai-material-type-result-e5.json (same 57 held-out materials).
set -eu

model="${INVESTWATCH_LLM_MODEL:-qwen3.5:4b-q4_K_M}"
split=heldout
pull=0
while [ $# -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --split) split="$2"; shift 2 ;;
    --pull) pull=1; shift ;;
    *) echo "Nieznana opcja: $1" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")/../.."
host="${OLLAMA_HOST:-127.0.0.1:11434}"
python=$(command -v python3.12 || command -v python3)
"$python" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Wymagany Python 3.11+ (brew install python@3.12)." >&2; exit 2; }
command -v ollama >/dev/null || { echo "Brak Ollama (brew install ollama albo aplikacja z ollama.com)." >&2; exit 2; }
curl -fsS -m 4 "http://$host/api/version" >/dev/null || { echo "Ollama nie odpowiada na $host. Uruchom aplikację albo: OLLAMA_CONTEXT_LENGTH=4096 ollama serve" >&2; exit 2; }
[ "$pull" = 1 ] && ollama pull "$model"

mkdir -p .runtime/mac
safe=$(printf '%s' "$model" | tr ':/' '__')
out=".runtime/mac/llm-$safe-$(date -u +%Y%m%dT%H%M%SZ).json"
swap_before=$(sysctl -n vm.swapusage 2>/dev/null || echo unknown)
memory=$(sysctl -n hw.memsize 2>/dev/null || echo unknown)

export OLLAMA_HOST="$host" INVESTWATCH_LLM=1 INVESTWATCH_LLM_MODEL="$model" INVESTWATCH_LLM_TIMEOUT="${INVESTWATCH_LLM_TIMEOUT:-120}"
"$python" -B -m analysis.inference status
# Cold start: unload the model so the first request includes loading (reported separately below).
curl -fsS -m 10 "http://$host/api/generate" -d "{\"model\":\"$model\",\"keep_alive\":0}" >/dev/null || true
started=$(date +%s)
"$python" -B -m analysis.inference evaluate --split "$split" > "$out.tmp"
finished=$(date +%s)
ps=$(curl -fsS -m 4 "http://$host/api/ps" || echo '{}')
swap_after=$(sysctl -n vm.swapusage 2>/dev/null || echo unknown)
version=$(curl -fsS -m 4 "http://$host/api/version" || echo '{}')

chip=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo unknown)
WALL=$((finished - started)) MEM="$memory" SWAP_BEFORE="$swap_before" SWAP_AFTER="$swap_after" \
OLLAMA_VERSION="$version" OLLAMA_PS="$ps" CHIP="$chip" "$python" - "$out.tmp" "$out" <<'PY'
import json, os, sys
env = os.environ
result = json.load(open(sys.argv[1]))
result["run"] = {"wallSeconds": int(env["WALL"]), "memBytes": env["MEM"], "swapBefore": env["SWAP_BEFORE"],
                 "swapAfter": env["SWAP_AFTER"], "ollamaVersion": json.loads(env["OLLAMA_VERSION"] or "{}"),
                 "ollamaPs": json.loads(env["OLLAMA_PS"] or "{}"), "chip": env["CHIP"]}
json.dump(result, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
m = result["metrics"]
print(f"{result['model']} {result.get('quantization')} digest {result.get('digest')}")
print(f"trafność {m['correct']}/{m['n']} = {m['accuracy']:.3f}, macro-F1 {m['macroF1']:.3f}, odrzucone przez walidator {result['rejectedShare']:.1%}")
print(f"czas: mediana {result['latencyMs']['median']} ms, max {result['latencyMs']['max']} ms, całość {result['run']['wallSeconds']} s")
print("porównaj (te same 57): E5+regresja 30/57 = 0,526; zawsze 'opinia' 23/57; reguły słownikowe 13/57")
print("próg przyjęcia LLM jako drugiego głosu: trafność >= 30/57 i odrzucenia walidatora <= 10%")
PY
rm -f "$out.tmp"
echo "Zapisano $out"
