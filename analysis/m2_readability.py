"""Auxiliary readability indicator for Polish risk warnings (UKNF criterion 9).

This is a team method, not a UKNF threshold. It flags a warning for an analyst when at least
two of four signals exceed the limits below. The audience assumed for public offer pages is
the average retail client ("klient detaliczny").

Signals and limits (team decision, documented in docs/lanes/2026-11-21-fable-e-m2.md):
  * FOG-PL (Gunning FOG adapted to Polish: hard word = 4 or more syllables) > 13
  * average sentence length > 20 words
  * share of long words (4+ syllables) > 25 %
  * unexplained jargon terms >= 2 (list below), or passive/impersonal forms plus negations
    together >= 3 in a warning of up to three sentences

Examples measured with this module:
  "Inwestowanie wiąże się z ryzykiem. Możesz stracić część pieniędzy."
      -> FOG-PL ≈ 4,1, 5 words per sentence, no jargon: readable.
  "Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty
   środków pieniężnych z powodu dźwigni finansowej."
      -> one 19-word sentence, jargon "CFD", "dźwignia finansowa"; this exact wording is the
         standard ESMA warning, so the indicator is reported but not used as a premise.
"""
import re

VOWELS = re.compile(r"[aąeęioóuy]+", re.I)
WORD = re.compile(r"[A-Za-zÀ-ÿĄąĆćĘęŁłŃńÓóŚśŹźŻż]+(?:-[A-Za-zÀ-ÿĄąĆćĘęŁłŃńÓóŚśŹźŻż]+)*")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"])")
JARGON = (
    r"dźwigni\w* finansow\w*", r"\blewar\w*", r"depozyt\w* zabezpieczając\w*", r"instrument\w* pochodn\w*",
    r"\bderywat\w*", r"\bspread\w*", r"\bswap\w*", r"margin call", r"\bstop loss", r"\bwolumen\w*",
    r"ekspozycj\w*", r"zmienno\w*", r"płynno\w*", r"pozycj\w* krótk\w*", r"\bshort\w*", r"rolowani\w*",
    r"punkt\w* swapow\w*", r"\bpips\w*", r"wartość nominaln\w*", r"\bduration\b", r"\bbenchmark\w*",
)
ACRONYM = re.compile(r"\b[A-Z]{2,5}\b")
EXPLAINED_ACRONYM = r"\b{0}\b\s*\(|\(\s*\b{0}\b\s*\)"
PASSIVE = re.compile(
    r"\b(?:zosta\w+|jest|są|był\w*|będzie|będą)\s+(?:\w+\s+)?\w+(?:any|ana|ane|ani|ony|ona|one|eni|ęty|ęta|ęte|ęci)\b"
    r"|\b\w+(?:ono|ano|ęto)\b", re.I)
NEGATION = re.compile(r"\bnie\b|\bżadn\w*|\bnigdy\b|\bbrak\w*", re.I)
ESMA_STANDARD = re.compile(r"(?:kontrakty|instrumenty) CFD są złożonymi instrumentami", re.I)
# FOG-PL above 13 is "trudny" on the Pisarek/Jasnopis scale; long-word share above a quarter is typical of legal prose.
LIMITS = {"fog": 13.0, "sentenceWords": 20.0, "longShare": 0.25, "jargon": 2, "passiveNegation": 3}


def syllables(word):
    return max(1, len(VOWELS.findall(word)))


def measure(text):
    """Return the indicator with every component, so the analyst sees why it fired."""
    text = " ".join((text or "").split())
    sentences = [s for s in SENTENCE.split(text) if WORD.search(s)] or ([text] if text else [])
    words = WORD.findall(text)
    if not words:
        return None
    long_words = [w for w in words if syllables(w) >= 4]
    per_sentence = len(words) / max(1, len(sentences))
    long_share = len(long_words) / len(words)
    fog = 0.4 * (per_sentence + 100 * long_share)
    jargon = sorted({re.search(p, text, re.I).group(0).lower() for p in JARGON if re.search(p, text, re.I)})
    acronyms = sorted({a for a in ACRONYM.findall(text) if a not in {"PL", "UE", "EU"}
                       and not re.search(EXPLAINED_ACRONYM.format(re.escape(a)), text)})
    passive = len(PASSIVE.findall(text))
    negations = len(NEGATION.findall(text))
    signals = {
        "fog": fog > LIMITS["fog"],
        "sentenceWords": per_sentence > LIMITS["sentenceWords"],
        "longShare": long_share > LIMITS["longShare"],
        "jargon": len(jargon) + len(acronyms) >= LIMITS["jargon"]
                  or (len(sentences) <= 3 and passive + negations >= LIMITS["passiveNegation"]),
    }
    return {
        "fog": round(fog, 1), "sentences": len(sentences), "words": len(words),
        "sentenceWords": round(per_sentence, 1), "longShare": round(long_share, 3),
        "longWords": long_words[:12], "jargon": jargon, "unexplainedAcronyms": acronyms,
        "passive": passive, "negations": negations, "signals": signals,
        "exceeded": [name for name, hit in signals.items() if hit],
        "difficult": sum(signals.values()) >= 2, "esmaStandard": bool(ESMA_STANDARD.search(text)),
        "limits": LIMITS, "method": "FOG-PL + długość zdań + długie wyrazy + żargon (wskaźnik pomocniczy zespołu)",
    }


def describe(result):
    if not result:
        return "Brak tekstu ostrzeżenia do oceny."
    parts = [f"FOG-PL {str(result['fog']).replace('.', ',')}", f"{str(result['sentenceWords']).replace('.', ',')} słów na zdanie",
             f"{round(result['longShare'] * 100)}% wyrazów co najmniej czterosylabowych"]
    terms = result["jargon"] + result["unexplainedAcronyms"]
    if terms:
        parts.append("terminy specjalistyczne: " + ", ".join(terms[:5]))
    return "; ".join(parts) + "."
