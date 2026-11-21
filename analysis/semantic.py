"""Suggest a source fragment by comparing local E5 embeddings with Polish examples."""

from functools import lru_cache
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import re

from .setup_semantic import DEFAULT_DIR, LOCK, MODEL_DIR_ENV, available

MAX_FRAGMENTS = 512
MAX_SOURCE_CHARS = 24_000
MAX_FRAGMENT_CHARS = 300
MAX_TOKENS = 128
MIN_MARGIN = 0.02
LOG = logging.getLogger(__name__)

# Examples describe linguistic signals and controls. No class encodes a legal conclusion.
EXAMPLES = {
    "M1": {
        "partnership": ("Deklaracja partnerstwa", (
            "Materiał powstał we współpracy z firmą inwestycyjną.",
            "Marka opłaciła wyprodukowanie tego odcinka lub zapewniła finansowanie publikacji.",
            "Powstanie audycji sfinansował dom maklerski.",
            "Partnerem odcinka jest broker, którego usługi przedstawia prowadzący.",
        )),
        "no_partnership": ("Zaprzeczenie partnerstwu", (
            "Odcinek nie jest sponsorowany ani finansowany przez brokera.",
            "Nie otrzymaliśmy zapłaty. Wymieniona firma nie finansowała publikacji.",
            "Twórca zaprzecza współpracy z firmą inwestycyjną, o której mówi.",
            "Mówimy o tej firmie niezależnie i nie mamy z nią umowy.",
        )),
        "neutral": ("Neutralna wzmianka", (
            "Autor omawia rynkowe wydarzenia w celu informacyjnym.",
            "Publikacja przedstawia edukacyjne informacje o rynku i polityce.",
            "Przywołano fakty o spółce i wynikach giełdy.",
        )),
    },
    "M2": {
        "benefit": ("Deklaracja korzyści", (
            "Firma reklamuje korzyść z inwestowania. Obiecuje wygodę i możliwość zysku.",
            "Inwestuj szybko i łatwo, zyskaj oszczędności bez prowizji.",
            "Rachunek inwestycyjny umożliwia zakup akcji bez opłat i atrakcyjne wyniki.",
        )),
        "risk_warning": ("Informacja o ryzyku", (
            "Inwestycje wiążą się z ryzykiem. Możesz stracić całość środków.",
            "Kontrakty CFD są złożone i powodują ryzyko szybkiej utraty pieniędzy.",
            "Wyniki z przeszłości nie gwarantują późniejszych zysków.",
        )),
        "neutral": ("Informacja ogólna", (
            "Informacje kontaktowe, nazwa i godziny pracy firmy.",
            "Artykuł opisuje fakty, daty, regulamin i aktualności.",
            "Strona informacyjna wyjaśnia, gdzie znaleźć dokument.",
        )),
    },
    "M3": {
        "personalized_advice": ("Wzmianka o indywidualnej rekomendacji", (
            "Po analizie potrzeb i sytuacji konkretnego klienta doradzimy zakup wybranego instrumentu.",
            "Na podstawie twojego majątku, celów i tolerancji ryzyka dobierzemy akcje do kupienia.",
            "Wskażemy klientowi, co kupić lub sprzedać w ramach spersonalizowanego portfela.",
            "Znamy twoje cele finansowe i wybierzemy dla ciebie fundusze inwestycyjne.",
        )),
        "general_education": ("Edukacja lub zaprzeczenie doradztwu", (
            "To edukacja finansowa i ogólne informacje o inwestycjach, bez rekomendacji dla klienta.",
            "W materiale omawiamy czym są fundusze, bez indywidualnego dobierania instrumentu.",
            "Nie świadczymy doradztwa inwestycyjnego i nie udzielamy spersonalizowanych rekomendacji.",
            "Opis przedstawia wyłącznie podstawy działania giełdy i rodzaje funduszy.",
        )),
        "neutral": ("Informacja ogólna", (
            "Firma opisuje swoje usługi, historię i obsługę klientów.",
            "Informacje mają charakter organizacyjny i dotyczą spotkania z opiekunem.",
            "Przedstawiamy warunki umowy, kontakt oraz dokumenty dla klienta.",
        )),
    },
}

METHOD_HASH = sha256(
    json.dumps(["windows-positive-guard-v2", EXAMPLES, MIN_MARGIN, MAX_FRAGMENTS, MAX_SOURCE_CHARS, MAX_FRAGMENT_CHARS, MAX_TOKENS],
               ensure_ascii=False, sort_keys=True).encode(),
).hexdigest()
MODEL = LOCK["repository"]
VERSION = f"{LOCK['revision'][:12]}-int8-{METHOD_HASH[:12]}"
BOUNDARY = re.compile(r"(?<=[.!?])\s+|[\r\n]+")


class Runtime:
    def __init__(self, directory):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        for name, spec in LOCK["files"].items():
            if not available(directory / name, spec):
                raise ValueError(f"Nieprawidłowy SHA-256 pliku {name}.")
        self.np = np
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.pad = self.tokenizer.token_to_id("<pad>")
        if self.pad is None:
            raise ValueError("Tokenizer jest niezgodny z przypiętym modelem.")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(directory / "model_quantized.onnx"), sess_options=options, providers=["CPUExecutionProvider"],
        )
        self.inputs = {item.name for item in self.session.get_inputs()}
        self.encode = lru_cache(maxsize=512)(self._encode_one)
        self.examples = {}

    def _encode_matrix(self, sentences):
        # The E5 model card specifies the query prefix for similarity and the masked mean.
        encoded = [self.tokenizer.encode(f"query: {sentence}").ids for sentence in sentences]
        np = self.np
        width = max(map(len, encoded))
        ids = np.full((len(encoded), width), self.pad, dtype=np.int64)
        attention = np.zeros_like(ids)
        for row, values in enumerate(encoded):
            ids[row, :len(values)] = values
            attention[row, :len(values)] = 1
        tensors = {"input_ids": ids, "attention_mask": attention, "token_type_ids": np.zeros_like(ids)}
        hidden = self.session.run(["last_hidden_state"], {name: tensors[name] for name in self.inputs})[0]
        mean = (hidden * attention[..., None]).sum(axis=1) / attention.sum(axis=1, keepdims=True)
        norm = (mean * mean).sum(axis=1, keepdims=True) ** 0.5
        return mean / norm

    def _encode_one(self, sentence):
        return self._encode_matrix([sentence])[0]

    def similar(self, module, sentence):
        if module not in self.examples:
            classes = EXAMPLES[module]
            prototypes = [example for _, examples in classes.values() for example in examples]
            vectors = iter(self._encode_matrix(prototypes))
            self.examples[module] = {
                kind: self.np.stack([next(vectors) for _ in examples])
                for kind, (_, examples) in classes.items()
            }
        vector = self.encode(sentence)
        # Elementwise multiplication avoids a threaded BLAS call for these short vectors.
        scores = {
            kind: float((examples * vector).sum(axis=1).max())
            for kind, examples in self.examples[module].items()
        }
        return sorted(scores.items(), key=lambda entry: entry[1], reverse=True)


@lru_cache(maxsize=1)
def runtime(directory, identities):
    # Identities make a replacement or failed setup retryable without restarting the worker.
    try:
        return Runtime(directory)
    except Exception as error:
        LOG.warning("Lokalny model semantyczny jest niedostępny (%s).", type(error).__name__)
        return None


def _fragments(capture):
    sources = [("title", capture.get("title"), {})]
    segments = capture.get("segments")
    if isinstance(segments, list):
        sources.extend(
            ("transcript", segment.get("text"), {k: segment[k] for k in ("start", "end") if k in segment})
            for segment in segments if isinstance(segment, dict)
        )
    sources.append(("description", capture.get("description"), {}))
    out = {}
    budget = MAX_SOURCE_CHARS
    for field, text, timing in sources:
        if not isinstance(text, str):
            continue
        for sentence in BOUNDARY.split(text[:budget]):
            for offset in range(0, len(sentence), MAX_FRAGMENT_CHARS):
                quote = sentence[offset:offset + MAX_FRAGMENT_CHARS].strip()
                if sum(char.isalpha() for char in quote) < 14:
                    continue
                out.setdefault(quote, {
                    "kind": "semantic", "field": field, "text": quote, "url": capture.get("url"),
                    **timing,
                })
                if len(out) >= MAX_FRAGMENTS:
                    return out
        budget -= min(len(text), budget)
        if budget == 0:
            break
    return out


def suggest(capture):
    """Compare bounded source fragments and prefer a positive candidate for review."""

    base = {"model": MODEL, "version": VERSION}
    module = capture.get("module")
    if module not in EXAMPLES:
        return {**base, "status": "empty"}
    fragments = _fragments(capture)
    if not fragments:
        return {**base, "status": "empty"}
    directory = Path(os.getenv(MODEL_DIR_ENV) or DEFAULT_DIR)
    try:
        stats = [(directory / name).stat() for name in LOCK["files"]]
        identities = tuple((info.st_mtime_ns, info.st_size) for info in stats)
    except OSError:
        return {**base, "status": "unavailable"}
    backend = runtime(directory, identities)
    if backend is None:
        return {**base, "status": "unavailable"}
    best = None
    best_positive = None
    positive = {"M1": "partnership", "M2": "benefit", "M3": "personalized_advice"}[module]
    try:
        for quote, evidence in fragments.items():
            (kind, cosine), (other_kind, other_cosine), *_ = backend.similar(module, quote)
            margin = cosine - other_cosine
            if best is None or margin > best[0]:
                best = margin, kind, cosine, other_kind, other_cosine, evidence
            if kind == positive and (best_positive is None or margin > best_positive[0]):
                best_positive = margin, kind, cosine, other_kind, other_cosine, evidence
    except Exception as error:
        LOG.warning("Nie udało się obliczyć podobieństwa (%s).", type(error).__name__)
        return {**base, "status": "unavailable"}
    margin, kind, cosine, other_kind, other_cosine, evidence = best_positive or best
    ambiguous = margin < MIN_MARGIN
    return {
        **base, "status": "ready", "class": "uncertain" if ambiguous else kind,
        "label": "Zbliżone podobieństwa" if ambiguous else EXAMPLES[module][kind][0],
        "leadingClass": kind, "minimumMargin": MIN_MARGIN,
        "fragment": evidence["text"], "cosineSimilarity": round(cosine, 6),
        "runnerUp": {"class": other_kind, "cosineSimilarity": round(other_cosine, 6)},
        "margin": round(margin, 6), "evidence": evidence,
        "scope": {"fragments": len(fragments), "sampledUpToChars": MAX_SOURCE_CHARS,
                  "tokensPerFragment": MAX_TOKENS,
                  "limited": sum(len(capture.get(k) or "") for k in ("title", "description")) +
                             sum(len(s.get("text") or "") for s in (capture.get("segments") or []) if isinstance(s, dict)) > MAX_SOURCE_CHARS
                             or len(fragments) >= MAX_FRAGMENTS},
    }


def review_suggestion(capture, semantic, finding=None):
    """A model cue for human triage; it cannot determine legality or identity."""
    if capture.get("module", "M1") == "M1" and finding is not None:
        from .engine import relation
        base = {"source": "rules", "version": finding.get("rulesVersion")}
        if finding.get("signalType") in {"declaration", "brand_cta"}:
            expected = {"declaration": 94, "brand_cta": 74}[finding["signalType"]]
            for evidence in finding.get("evidence", []):
                if evidence.get("kind") in {"audio", "description"} and relation(evidence.get("text", ""), capture.get("brand"))[0] == expected:
                    return {**base, "state": "review", "reason": "Reguły wskazują deklarację albo zachętę przy marce do sprawdzenia.", "evidence": evidence}
            return {**base, "state": "uncertain", "reason": "Nie znaleziono fragmentu potwierdzającego wskazany sygnał."}
        return {**base, "state": "no_signal", "reason": "Reguły nie wskazały deklaracji ani zachęty przy marce w zbadanym zakresie."}
    base = {"source": "semantic", "model": semantic.get("model"), "version": semantic.get("version")}
    if capture.get("module") != "M3":
        return {**base, "state": "unavailable", "reason": "Flaga modelowa przeglądu nie jest jeszcze ustalona dla tego modułu."}
    if semantic.get("status") != "ready":
        return {**base, "state": "unavailable", "reason": "Model nie zwrócił wyniku; dostępne są reguły."}
    evidence = semantic.get("evidence") or {}
    quote = evidence.get("text", "")
    if semantic.get("class") == "uncertain":
        return {**base, "state": "uncertain", "reason": "Podobieństwa są zbliżone; potrzebna ocena człowieka.", "evidence": evidence}
    module = capture.get("module")
    positive = {"M1": "partnership", "M2": "benefit", "M3": "personalized_advice"}.get(module)
    negated = re.search(r"\b(?:nie|bez|brak|żadn\w*)\b.{0,90}\b(?:rekomend\w*|doradz\w*|dobier\w*|współprac\w*|partner\w*|sponsor\w*|finansow\w*)", quote, re.I)
    relation = re.search(r"\b(?:współprac\w*|partner\w*|sponsor\w*|finansow\w*|sfinansow\w*|opłaci\w*|pokrył\w*|wynagrodzeni\w*|zapłat\w*)\b", quote, re.I)
    personal_action = (re.search(r"\b(?:podpowiad\w*|rekomend\w*|doradz\w*|dob(?:ier|ior)\w*|wskaż\w*|wybierz\w*)\b", quote, re.I)
                       and re.search(r"\b(?:ty|ci|tobie|two\w*|klient\w*|państw\w*|ciebie)\b", quote, re.I))
    if (semantic.get("class") == positive and not negated and (module != "M1" or relation)
            and (module != "M3" or personal_action)):
        return {**base, "state": "review", "reason": "Model wskazuje fragment do przeglądu; to nie jest rozstrzygnięcie prawne.",
                "evidence": evidence, "score": semantic.get("cosineSimilarity")}
    if semantic.get("class") == positive:
        return {**base, "state": "uncertain", "reason": "Model wskazał fragment, ale brakuje jednoznacznej podstawy do powiązania go z sygnałem.",
                "evidence": evidence}
    return {**base, "state": "no_signal", "reason": "Model nie wskazał dostatecznie jednoznacznego sygnału w zbadanym zakresie.",
            "evidence": evidence}
