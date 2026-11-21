"""The card of view 2 (`GET /v1/cases/{key}?schema=2`): one story, human text for measurements, short moment labels.

Pure functions of the stored case. The list rows (`summary_of_case`) are not touched, they need the v1 fields internally.
"""
import re

LEGACY = ("score", "reviewSuggestion", "summary", "signalType")
CHANNEL = {"transcript": "speech", "description": "description", "platform": "platform_flag", "frame": "frame"}
STRENGTH = ("speech", "frame", "description", "platform_flag")


def _where(viewport):
    return "telefonie" if "phone" in str(viewport) else "komputerze"


def human_text(row):
    """One sentence about the measurement of a check row; raw values stay in `measurements`."""
    measures = [m for m in row.get("measurements") or [] if isinstance(m, dict)]
    rid, state = row.get("id"), row.get("state")
    if rid == "3":
        pairs = [m for m in measures if isinstance(m.get("distancePx"), (int, float)) and m.get("warningQuote")]
        if pairs:
            far = max(pairs, key=lambda m: m["distancePx"])
            return f"ostrzeżenie {int(far['distancePx'])} px poniżej twierdzenia na {_where(far.get('viewport'))}"
    if rid == "4":
        sized = [m for m in measures if m.get("px") and m.get("dominantPx")]
        if sized:
            low = min(sized, key=lambda m: m.get("ratio") or 1)
            if state == "przesłanka":
                return f"ostrzeżenie mniejszą czcionką: {low['px']} px wobec {low['dominantPx']} px treści"
            return f"ostrzeżenie {low['px']} px, treść {low['dominantPx']} px"
    if rid == "8":
        phone = [m for m in measures if "phone" in str(m.get("viewport")) and m.get("px")]
        if phone:
            return f"ostrzeżenie na telefonie: {phone[0]['px']} px"
    if rid == "9":
        read = next((m["readability"] for m in measures if isinstance(m.get("readability"), dict)), None)
        if read:
            signals = read.get("signals") or {}
            parts = [text for key, text in (("sentenceWords", "długie zdania"), ("jargon", "terminy fachowe"), ("longShare", "długie wyrazy"),
                                            ("fog", "wysoki wskaźnik trudności")) if signals.get(key)]
            return "tekst trudny: " + ", ".join(parts) if read.get("difficult") and parts else "tekst czytelny"
    return None


def _short(text, limit=56):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def moment_labels(case):
    """Short, different labels for the moments of the decision (the quote or the time, never the name of the requirement)."""
    decision = case.get("reviewDecision")
    if not isinstance(decision, dict) or not decision.get("moments"):
        return
    by_id = {e.get("id"): e for e in case.get("evidence") or [] if isinstance(e, dict)}
    seen = set()
    for number, moment in enumerate(decision["moments"], 1):
        evidence = by_id.get(moment.get("evidenceId")) or {}
        quote = moment.get("quote") or evidence.get("text") or ""
        start = moment.get("start")
        clock = f"{int(start) // 60}:{int(start) % 60:02d} " if isinstance(start, (int, float)) else ""
        label = f"{clock}„{_short(quote)}”" if quote else f"{clock}moment {number}".strip()
        if label in seen:
            label = f"{label} ({number})"
        seen.add(label)
        moment["label"] = label


def disclosure_kinds(case):
    """`kinds`: channels of the disclosure in order of strength (speech, frame, description, platform flag)."""
    relation = case.get("adRelationship") if isinstance(case.get("adRelationship"), dict) else {}
    disclosure = relation.get("disclosure") if isinstance(relation.get("disclosure"), dict) else None
    if not disclosure:
        return
    channel = CHANNEL.get(disclosure.get("where"))
    kinds = [channel] if channel else []
    flag = ((case.get("coverage") or {}).get("modalities") or {}).get("platformFlags") or {}
    if flag.get("paidPromotion") is True and "platform_flag" not in kinds:
        kinds.append("platform_flag")
    disclosure["kinds"] = sorted(dict.fromkeys(kinds), key=STRENGTH.index)
    if disclosure.get("kind") == "platform_flag" and channel and channel != "platform_flag":
        disclosure["kind"] = f"{channel}_marking"


def consistent_decision(case):
    """A post or ad of M2 without a card: the card says what the row says (route, score), not null."""
    if case.get("module") != "M2" or case.get("reviewDecision"):
        return
    suggestion = case.get("reviewSuggestion") if isinstance(case.get("reviewSuggestion"), dict) else {}
    route = case.get("route") or {"unavailable": "insufficient", "no_signal": "no_signal"}.get(suggestion.get("state"))
    scope = case.get("m2Scope") if isinstance(case.get("m2Scope"), dict) else {}
    reason = suggestion.get("reason") or scope.get("label") or "Brak pomiaru strony dla tego materiału."
    case["reviewDecision"] = {"route": route, "reason": reason, "reasons": [reason], "moments": [], "queueEligible": False,
                              "completeReason": "media_unexamined" if route == "insufficient" else None, "decidedBy": "rules",
                              "version": case.get("rulesVersion"), "missing": [], "claim": None, "requirement": None, "alternative": None}
    if not isinstance(case.get("reviewScore"), dict):
        case["reviewScore"] = {"state": "computed", "value": case.get("score"), "scale": "0-100", "band": None, "components": [],
                               "meaning": "Wynik reguł tekstu; obrazu i wideo nie badano", "rulesVersion": case.get("rulesVersion")}


def card_view(case):
    """View 2 of one card: coherent, v1 fields under `legacy` (the list rows and view 1 are unchanged)."""
    case = dict(case)
    consistent_decision(case)
    decision = case.get("reviewDecision") if isinstance(case.get("reviewDecision"), dict) else None
    if decision:
        decision = {**decision, "moments": [dict(m) for m in decision.get("moments") or []]}
        alternative = (decision.get("alternative") or "").strip()
        if alternative:
            decision["reasons"] = [r for r in decision.get("reasons") or [] if not (isinstance(r, str) and r.strip() == alternative)]
        case["reviewDecision"] = decision
        moment_labels(case)
    if isinstance(case.get("adRelationship"), dict):
        case["adRelationship"] = {**case["adRelationship"], "disclosure": dict(case["adRelationship"].get("disclosure") or {})} \
            if case["adRelationship"].get("disclosure") else case["adRelationship"]
        disclosure_kinds(case)
    for name in ("checks",):
        if isinstance(case.get(name), list):
            case[name] = [{**r, "humanText": human_text(r)} if isinstance(r, dict) else r for r in case[name]]
    card = case.get("m2Card")
    if isinstance(card, dict) and isinstance(card.get("rows"), list):
        checks = {r.get("id"): r for r in case.get("checks") or [] if isinstance(r, dict)}
        card = {**card, "rows": [{**r, "humanText": human_text(checks.get(r.get("id")) or r)} for r in card["rows"]]}
        if isinstance(card.get("firm"), dict):
            from .store import clean_firm
            card = {**card, "firm": {**card["firm"], "name": clean_firm(card["firm"].get("name"))}}
        case["m2Card"] = card
    if decision:
        case["legacy"] = {k: case.pop(k) for k in LEGACY if k in case}
    return case
