"""Material type (promocja/edukacja/informacja/opinia) from local E5 embeddings and logistic regression.

Pipeline: preprocessing (HTML, Unicode, URLs, timestamps, repeated lines, duplicate materials) ->
E5 tokens and a 384-dimensional embedding -> softmax layer -> class with probability.
The label is a descriptive feature for the analyst. It never changes the route or the score.

The preprocessing part uses only the standard library, so the Ollama client can share it.
"""
import argparse
from functools import lru_cache
import gzip
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import random
import re
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = Path(__file__).with_name("material-type-weights.json")
LABELS = ROOT / "fixtures/labeled/ai-material-type.json"
REPLAY = ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz"
CLASSES = ("promocja", "edukacja", "informacja", "opinia")
TASK = "material_type"
PREPROCESS_VERSION = "pp-1"
MAX_TEXT_CHARS = 1200
MAX_TOKENS = 256
MIN_CONFIDENCE = 0.5

TAG = re.compile(r"<[^>]{0,400}>")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
TIMESTAMP_LINE = re.compile(r"^\s*(?:\(?\d{1,2}:)?\d{1,2}:\d{2}\)?\s*[-–—:]?\s*")
SEPARATOR = re.compile(r"^[\W_]{3,}$")
SPACES = re.compile(r"[ \t ​]+")
POLISH = re.compile(r"[ąćęłńóśźż]", re.I)


def clean_text(text, limit=None):
    """Remove HTML, normalise Unicode and whitespace, drop URLs, chapter timestamps and repeated lines."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", html.unescape(TAG.sub(" ", text)))
    seen, lines = set(), []
    for line in text.splitlines():
        line = TIMESTAMP_LINE.sub("", EMAIL.sub(" ", URL.sub(" ", line)))
        line = SPACES.sub(" ", line).strip(" -–—|•:")
        if not line or SEPARATOR.match(line):
            continue
        key = line.casefold()
        if key in seen:  # boilerplate repeated inside one description
            continue
        seen.add(key)
        lines.append(line)
    cleaned = "\n".join(lines)
    return cleaned[:limit] if limit else cleaned


def material_text(capture, limit=MAX_TEXT_CHARS):
    """Title and cleaned description: the input of both the classifier and the LLM second opinion."""
    title = clean_text(capture.get("title"))
    description = clean_text(capture.get("description"))
    return (f"{title}\n{description}" if title else description)[:limit].strip()


def text_sha256(text):
    return sha256(text.encode("utf-8")).hexdigest()


def dedupe(captures):
    """Keep the first material for every identical preprocessed text (reposts, mirrored uploads)."""
    seen, out = set(), []
    for capture in captures:
        key = text_sha256(material_text(capture).casefold())
        if key not in seen:
            seen.add(key)
            out.append(capture)
    return out


def load_replay(path=REPLAY):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)["captures"]


def creator_split(creator_id):
    """Split by creator, never by video, so one channel's style cannot leak into the held-out set."""
    return "heldout" if int(sha256(f"ai-material-type:{creator_id}".encode()).hexdigest(), 16) % 5 < 2 else "tuning"


def sample(captures, size=160, per_creator=3, seed=20261121):
    polish = [c for c in captures if POLISH.search(material_text(c)) and len(material_text(c)) >= 80]
    pool = dedupe(sorted(polish, key=lambda c: c["id"]))
    random.Random(seed).shuffle(pool)
    counts, chosen = {}, []
    for capture in pool:
        creator = capture.get("creatorId")
        if counts.get(creator, 0) >= per_creator:
            continue
        counts[creator] = counts.get(creator, 0) + 1
        chosen.append(capture)
        if len(chosen) == size:
            break
    return chosen


def labeled_examples(labels_path=LABELS, replay_path=REPLAY):
    """Join the agent labels with the replay text and check that the text is unchanged."""
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in load_replay(replay_path)}
    rows = []
    for item in labels["items"]:
        capture = by_id[item["id"]]
        text = material_text(capture)
        if text_sha256(text) != item["textSha256"]:
            raise ValueError(f"Tekst materiału {item['id']} różni się od oznaczonego.")
        rows.append({**item, "text": text, "capture": capture})
    return labels, rows


# --- E5 encoder and softmax layer (numpy imported lazily) ---------------------------------------

class Encoder:
    def __init__(self, directory):
        from .semantic import Runtime
        self.runtime = Runtime(directory)
        self.runtime.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.np = self.runtime.np

    def encode(self, texts, batch=8):
        parts = [self.runtime._encode_matrix(texts[i:i + batch]) for i in range(0, len(texts), batch)]
        return self.np.concatenate(parts) if parts else self.np.zeros((0, 384))


def semantic_dir():
    from .setup_semantic import DEFAULT_DIR, MODEL_DIR_ENV
    return Path(os.getenv(MODEL_DIR_ENV) or DEFAULT_DIR)


@lru_cache(maxsize=1)
def _encoder(directory, identities):
    try:
        return Encoder(Path(directory))
    except Exception:
        return None


def encoder():
    from .setup_semantic import LOCK
    directory = semantic_dir()
    try:
        identities = tuple((directory / name).stat().st_size for name in LOCK["files"])
    except OSError:
        return None
    return _encoder(str(directory), identities)


def fit(np, x, y, l2, epochs=600, rate=0.05):
    """Multinomial logistic regression, full-batch gradient descent with L2 on the weights."""
    n, d = x.shape
    k = len(CLASSES)
    w, b = np.zeros((d, k)), np.zeros(k)
    onehot = np.eye(k)[y]
    for _ in range(epochs):
        p = softmax(np, x @ w + b)
        grad = p - onehot
        w -= rate * (x.T @ grad / n + l2 * w)
        b -= rate * grad.mean(axis=0)
    return w, b


def softmax(np, z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def confusion(expected, predicted, classes=CLASSES + ("nieustalone",)):
    matrix = {e: {p: 0 for p in classes} for e in CLASSES}
    for e, p in zip(expected, predicted):
        matrix[e][p] += 1
    correct = sum(e == p for e, p in zip(expected, predicted))
    answered = sum(p != "nieustalone" for p in predicted)
    per_class = {}
    for c in CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[e][c] for e in CLASSES if e != c)
        fn = sum(v for p, v in matrix[c].items() if p != c)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
        per_class[c] = {"support": tp + fn, "precision": precision, "recall": recall, "f1": f1}
    return {"n": len(expected), "correct": correct, "accuracy": correct / len(expected) if expected else None,
            "answered": answered, "abstained": len(expected) - answered,
            "accuracyAnswered": (correct / answered) if answered else None,
            "macroF1": sum(v["f1"] for v in per_class.values()) / len(CLASSES), "perClass": per_class,
            "matrix": matrix}


def keyword_baseline(text):
    """Dictionary rules written before the held-out evaluation; the comparison point for the model."""
    t = text.casefold()
    if re.search(r"#reklama|\breklama\b|sponsor|partnerem|kod (?:rabatow|promocyj)|zapisz si[eę]|kup (?:teraz|kurs)|"
                 r"rabat|promocj|bonus|otw[oó]rz (?:konto|rachunek)|za[lł][oó]ż (?:konto|rachunek)|webinar", t):
        return "promocja"
    if re.search(r"jak (?:zacz|inwest|kupi|dzia[lł])|poradnik|czym (?:jest|s[aą])|podstaw|krok po kroku|wyja[sś]niam|"
                 r"dla pocz[aą]tkuj|kurs\b|lekcj|edukac", t):
        return "edukacja"
    if re.search(r"moim zdaniem|uwa[zż]am|czy warto|m[oó]j portfel|kupuj[eę]|sprzedaj[eę]|prognoz|\?|opini|komentarz", t):
        return "opinia"
    return "informacja"


def train(labels_path=LABELS, replay_path=REPLAY, out=WEIGHTS, grid=(1e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0)):
    labels, rows = labeled_examples(labels_path, replay_path)
    tuning = [r for r in rows if r["split"] == "tuning"]
    enc = encoder()
    if enc is None:
        raise SystemExit("Brak wag E5: uruchom python3 -m analysis.setup_semantic.")
    np = enc.np
    raw = enc.encode([r["text"] for r in tuning])
    # E5 vectors share a large common component; centring and scaling makes the classes separable.
    mean, scale = raw.mean(axis=0), raw.std(axis=0) + 1e-6
    x = (raw - mean) / scale
    y = np.array([CLASSES.index(r["label"]) for r in tuning])
    creators = sorted({r["creatorId"] for r in tuning})
    folds = [creators[i::5] for i in range(5)]
    scores = {}
    for l2 in grid:  # grouped 5-fold CV inside the tuning creators only
        hits = 0
        for fold in folds:
            test = np.array([r["creatorId"] in fold for r in tuning])
            m, sc = raw[~test].mean(axis=0), raw[~test].std(axis=0) + 1e-6
            w, b = fit(np, (raw[~test] - m) / sc, y[~test], l2)
            x_test = (raw[test] - m) / sc
            hits += int((softmax(np, x_test @ w + b).argmax(axis=1) == y[test]).sum())
        scores[l2] = hits / len(tuning)
    l2 = max(grid, key=lambda value: (scores[value], value))
    w, b = fit(np, x, y, l2)
    from .setup_semantic import LOCK
    body = {"task": TASK, "classes": list(CLASSES), "preprocess": PREPROCESS_VERSION, "maxTokens": MAX_TOKENS,
            "maxTextChars": MAX_TEXT_CHARS, "encoder": {"repository": LOCK["repository"], "revision": LOCK["revision"],
                                                        "onnxSha256": LOCK["files"]["model_quantized.onnx"]["sha256"]},
            "trainedOn": {"labels": Path(labels_path).name, "labelsSha256": sha256(Path(labels_path).read_bytes()).hexdigest(),
                          "n": len(tuning), "split": "tuning", "creators": len(creators)},
            "l2": l2, "cvAccuracyByL2": {str(k): round(v, 4) for k, v in scores.items()},
            "mean": np.round(mean, 6).tolist(), "scale": np.round(scale, 6).tolist(),
            "weights": np.round(w, 6).tolist(), "bias": np.round(b, 6).tolist()}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["version"] = f"mt-e5lr-1-{sha256(payload.encode()).hexdigest()[:12]}"
    Path(out).write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return body


@lru_cache(maxsize=2)
def _weights(path, mtime):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["digest"] = sha256(Path(path).read_bytes()).hexdigest()
    return data


def load_weights(path=WEIGHTS):
    try:
        return _weights(str(path), Path(path).stat().st_mtime_ns)
    except (OSError, ValueError):
        return None


def unavailable(reason, weights=None):
    return {"task": TASK, "engine": "e5-logreg", "status": "unavailable", "reason": reason, "label": None,
            "confidence": None, "quote": None, "modelId": (weights or {}).get("encoder", {}).get("repository"),
            "version": (weights or {}).get("version"), "digest": (weights or {}).get("digest"),
            "promptVersion": None, "latencyMs": None, "affectsDecision": False}


def classify_texts(texts, weights=None):
    weights = weights or load_weights()
    enc = encoder()
    if weights is None or enc is None:
        return None
    np = enc.np
    x = (enc.encode(list(texts)) - np.array(weights["mean"])) / np.array(weights["scale"])
    return softmax(np, x @ np.array(weights["weights"]) + np.array(weights["bias"]))


def classify(capture):
    """Annotation for one material; status 'unavailable' when weights or E5 are missing."""
    weights = load_weights()
    if weights is None:
        return unavailable("brak pliku wag klasyfikatora")
    text = material_text(capture)
    if len(text) < 20:
        return {**unavailable("za mało tekstu", weights), "status": "empty"}
    started = time.monotonic()
    try:
        probabilities = classify_texts([text], weights)
    except Exception as error:
        return unavailable(f"błąd modelu ({type(error).__name__})", weights)
    if probabilities is None:
        return unavailable("model E5 niedostępny", weights)
    row = probabilities[0]
    best = int(row.argmax())
    confidence = float(row[best])
    return {"task": TASK, "engine": "e5-logreg", "status": "ready",
            "label": CLASSES[best] if confidence >= MIN_CONFIDENCE else "nieustalone",
            "leadingLabel": CLASSES[best], "confidence": round(confidence, 4),
            "probabilities": {c: round(float(p), 4) for c, p in zip(CLASSES, row)},
            "quote": None, "modelId": weights["encoder"]["repository"], "version": weights["version"],
            "digest": weights["digest"], "promptVersion": None, "inputSha256": text_sha256(text),
            "latencyMs": round((time.monotonic() - started) * 1000, 1), "affectsDecision": False}


def evaluate(labels_path=LABELS, replay_path=REPLAY, split="heldout"):
    weights = load_weights()
    _, rows = labeled_examples(labels_path, replay_path)
    rows = [r for r in rows if split == "all" or r["split"] == split]
    expected = [r["label"] for r in rows]
    started = time.monotonic()
    probabilities = classify_texts([r["text"] for r in rows], weights)
    seconds = time.monotonic() - started
    if probabilities is None:
        raise SystemExit("Model niedostępny.")
    leading = [CLASSES[int(i)] for i in probabilities.argmax(axis=1)]
    gated = [label if float(p.max()) >= MIN_CONFIDENCE else "nieustalone" for label, p in zip(leading, probabilities)]
    majority = max(CLASSES, key=lambda c: sum(r["label"] == c for r in labels_tuning(labels_path)))
    errors = [{"id": r["id"], "expected": r["label"], "predicted": p, "confidence": round(float(q.max()), 3),
               "title": r["capture"].get("title")} for r, p, q in zip(rows, leading, probabilities) if p != r["label"]]
    return {"split": split, "version": weights["version"], "digest": weights["digest"],
            "secondsPerMaterial": round(seconds / max(len(rows), 1), 4),
            "model": confusion(expected, leading), "modelWithAbstention": confusion(expected, gated),
            "keywordRules": confusion(expected, [keyword_baseline(r["text"]) for r in rows]),
            "majorityClass": {"label": majority, **confusion(expected, [majority] * len(rows))},
            "errors": errors}


def labels_tuning(labels_path=LABELS):
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    return [i for i in labels["items"] if i["split"] == "tuning"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sample", help="Wypisz kandydatów do oznaczenia (bez etykiet).")
    s.add_argument("--size", type=int, default=160)
    sub.add_parser("train", help="Trenuj na zbiorze strojenia i zapisz wagi.")
    e = sub.add_parser("evaluate", help="Oceń na zbiorze odłożonym.")
    e.add_argument("--split", default="heldout", choices=("heldout", "tuning", "all"))
    c = sub.add_parser("classify", help="Sklasyfikuj materiał z pliku JSON.")
    c.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "sample":
        for capture in sample(load_replay(), args.size):
            text = material_text(capture)
            print(json.dumps({"id": capture["id"], "creatorId": capture["creatorId"],
                              "split": creator_split(capture["creatorId"]), "textSha256": text_sha256(text),
                              "text": text[:600]}, ensure_ascii=False))
    elif args.command == "train":
        body = train()
        print(json.dumps({k: body[k] for k in ("version", "l2", "cvAccuracyByL2", "trainedOn")}, ensure_ascii=False))
    elif args.command == "evaluate":
        print(json.dumps(evaluate(split=args.split), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(classify(json.loads(args.path.read_text(encoding="utf-8"))), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
