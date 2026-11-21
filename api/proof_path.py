"""`proofPath[]`: the ordered verification steps of a case, each with a state and one sentence (view 2 of the card).

State: `ok` the step was done and found nothing against the case or only confirms it, `suspect` the step supports the
suspicion, `refuted` the step contradicts it (for instance a disclosure in speech), `gap` not examined, `skipped` not
applicable. A pure function of the case record: no database, no network.
"""
import re


def _clock(seconds):
    if not isinstance(seconds, (int, float)):
        return None
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


def _dig(value, *path):
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _step(id, label, state, detail, at=None, deep_link=None):
    return {"id": id, "label": label, "state": state, "detail": detail, "at": at, "deepLink": deep_link}


def _link(case, seconds):
    url = case.get("url") or ""
    if seconds is not None and "youtube.com" in url:
        return f"{url}{'&' if '?' in url else '?'}t={int(seconds)}s"
    return url or None


def _discovery_step(case):
    entry = next(iter(case.get("discovery") or []), None) or {}
    how = entry.get("reason") or entry.get("method") or "nie ustalono"
    query = f": „{entry['query']}”" if entry.get("query") else ""
    return _step("discovery", "Odkrycie", "ok" if entry else "gap", f"{how}{query}")


def m1(case):
    relation = case.get("adRelationship") if isinstance(case.get("adRelationship"), dict) else {}
    disclosure = relation.get("disclosure") if isinstance(relation.get("disclosure"), dict) else {}
    coverage = case.get("coverage") if isinstance(case.get("coverage"), dict) else {}
    modalities = coverage.get("modalities") if isinstance(coverage.get("modalities"), dict) else {}
    where = disclosure.get("where")
    seconds = next((e.get("start") for e in case.get("evidence") or [] if isinstance(e, dict) and e.get("id") == disclosure.get("evidenceId")), None)
    kinds = disclosure.get("kinds") or ([disclosure["kind"]] if disclosure.get("kind") else [])
    steps = [_discovery_step(case)]
    status = relation.get("status")
    in_description = where == "description"
    if status in ("declared", "documented", "probable"):
        steps.append(_step("description", "Opis", "refuted" if in_description else "suspect",
                           ("Oznaczenie współpracy w opisie: " + (disclosure.get("text") or "") if in_description
                            else f"Relacja z firmą: {relation.get('basis') or status}; w opisie bez oznaczenia")))
    else:
        steps.append(_step("description", "Opis", "ok" if modalities.get("description") else "gap", "Nie znaleziono dowodu relacji z firmą w opisie"))
    flag = (modalities.get("platformFlags") or {})
    paid = flag.get("paidPromotion")
    if flag.get("state") == "observed" and paid is True:
        steps.append(_step("platformFlag", "Oznaczenie płatnej promocji", "refuted", "tak: platforma oznacza materiał jako płatną promocję"))
    elif flag.get("state") == "observed":
        steps.append(_step("platformFlag", "Oznaczenie płatnej promocji", "ok", "nie: platforma nie oznaczyła materiału"))
    else:
        steps.append(_step("platformFlag", "Oznaczenie płatnej promocji", "gap", "nie sprawdzono"))
    transcript = modalities.get("transcript") or {}
    if where == "transcript" or (where and where.startswith("speech")):
        steps.append(_step("speech", "Mowa", "refuted", f"Oznaczenie znalezione w mowie ({_clock(seconds)}): „{disclosure.get('text') or ''}”",
                           at=seconds, deep_link=_link(case, seconds)))
    elif transcript.get("state") == "full":
        steps.append(_step("speech", "Mowa", "suspect" if status in ("declared", "documented", "probable") else "ok",
                           f"Zbadano całą mowę (0:00–{_clock(transcript.get('durationSec')) or '?'}): oznaczenia nie znaleziono"))
    else:
        steps.append(_step("speech", "Mowa", "gap", "Mowy nie zbadano (transkrypcja czeka lub jest niedostępna)"))
    frames = modalities.get("frames") or {}
    moments = frames.get("moments") or []
    if where == "frame":
        steps.append(_step("frames", "Kadry", "refuted", "Oznaczenie widoczne w kadrze", at=seconds, deep_link=_link(case, seconds)))
    elif frames.get("state") == "selected_moments" and moments:
        steps.append(_step("frames", "Kadry", "ok", f"{len(moments)} kadrów w sekundach: " + ", ".join(str(int(m)) for m in moments[:6])
                           + "; tekst z obrazu nie jest odczytywany automatycznie", at=moments[0], deep_link=_link(case, moments[0])))
    else:
        steps.append(_step("frames", "Kadry", "gap", "Kadrów nie zbadano"))
    firm = relation.get("firm") if isinstance(relation.get("firm"), dict) else {}
    names = [c.get("name") for c in firm.get("candidates") or [] if isinstance(c, dict) and c.get("name")]
    registry = case.get("adRegistry") if isinstance(case.get("adRegistry"), dict) else {}
    steps.append(_step("firm", "Firma w wykazie KNF", "ok" if names or firm.get("mention") else "gap",
                       ("Dopasowania: " + "; ".join(names[:3])) if names else registry.get("identityNote") or "Brak dopasowania w wykazie"))
    model = case.get("model") if isinstance(case.get("model"), dict) else None
    if model and model.get("status") == "ready" and model.get("label"):
        steps.append(_step("model", "Typ materiału (model)", "ok", f"{model.get('label')} (opis; nie zmienia decyzji)"))
    second = case.get("secondOpinion") if isinstance(case.get("secondOpinion"), dict) else None
    if second and second.get("status") == "ready":
        steps.append(_step("secondOpinion", "Drugi głos (model)", "suspect" if second.get("needsReview") else "ok",
                           ("Rozbieżność z regułami: " if second.get("needsReview") else "Zgodny z regułami: ") + (second.get("quote") or second.get("verdict") or ""),
                           at=_dig(second, "locator", "seconds"), deep_link=_link(case, _dig(second, "locator", "seconds"))))
    steps.append(_decision(case))
    return steps


def _decision(case):
    decision = case.get("reviewDecision") if isinstance(case.get("reviewDecision"), dict) else {}
    route = case.get("route") or decision.get("route")
    text = {"refer": "Do sprawdzenia przez analityka", "complete": "Do uzupełnienia", "no_signal": "Brak przesłanki do kontroli",
            "insufficient": "Za mało danych"}.get(route, "Brak oceny reguł")
    return _step("decision", "Decyzja", "suspect" if route == "refer" else "refuted" if route == "no_signal" and decision.get("reason") else "ok" if route else "gap",
                 f"{text}. {decision.get('reason') or ''}".strip())


def m2(case):
    card = case.get("m2Card") if isinstance(case.get("m2Card"), dict) else None
    if card is None:
        text = (case.get("textSignals") or {})
        steps = [_step("read", "Odczyt", "ok" if case.get("description") else "gap", "Tekst posta lub reklamy (obrazu i wideo nie badano)"),
                 _step("claim", "Twierdzenie", "suspect" if text.get("benefitClaim") else "ok",
                       ("Korzyść w tekście: „" + "”, „".join(text.get("benefitClaims") or []) + "”") if text.get("benefitClaim") else "W tekście nie znaleziono twierdzenia o korzyści"),
                 _step("warning", "Ostrzeżenie", "ok" if text.get("riskWarningInText") else "gap",
                       "Ostrzeżenie o ryzyku w tekście" if text.get("riskWarningInText") else "W tekście brak ostrzeżenia; w grafice nie badano"),
                 _step("firm", "Firma w wykazie KNF", "ok" if case.get("firmRelation") else "gap",
                       (case.get("firmRelation") or {}).get("label") or "Brak dopasowania"), _decision(case)]
        return steps
    rows = card.get("rows") or []
    premises = [r for r in rows if r.get("state") == "przesłanka"]
    lead = next(iter(premises), None)
    measure = next((m for r in premises for m in r.get("measurements") or []), None)
    steps = [_step("read", "Odczyt strony", "ok", "Przeglądarka: " + ", ".join(card.get("viewports") or []) + "; tekst zwiniętych elementów też sprawdzono"),
             _step("claim", "Twierdzenie", "suspect" if lead else "ok", (lead or {}).get("evidence") or "Nie znaleziono twierdzenia bez ostrzeżenia")]
    if measure:
        steps.append(_step("warning", "Ostrzeżenie i pomiar", "suspect", measure_text(measure)))
    else:
        steps.append(_step("warning", "Ostrzeżenie i pomiar", "ok", "Pomiar nie wykazał przesłanki"))
    firm = card.get("firm") or {}
    steps.append(_step("firm", "Firma w wykazie KNF", "ok" if firm.get("registryId") else "gap",
                       f"{firm.get('name') or firm.get('brand') or 'brak'} ({firm.get('entityLabel') or 'rodzaj podmiotu nieustalony'})"))
    steps.append(_decision(case))
    return steps


def measure_text(m):
    """A measurement in words for a person; the raw values stay in the structured fields of the measurement."""
    bits = []
    distance = m.get("distancePx")
    where = "na telefonie" if "phone" in str(m.get("viewport")) else "na komputerze"
    if isinstance(distance, (int, float)) and m.get("warningQuote"):
        bits.append(f"ostrzeżenie {int(distance)} px od twierdzenia {where}")
    if m.get("px") and m.get("warningQuote") is None:
        bits.append(f"tekst {m['px']} px")
    return "; ".join(bits) or "Pomiar położenia i wielkości tekstu w przeglądarce"


def m3(case):
    axes = case.get("axes") if isinstance(case.get("axes"), dict) else {}
    identity = case.get("identity") if isinstance(case.get("identity"), dict) else {}
    quote = lambda axis: next((e.get("quote") for e in (axes.get(axis) or {}).get("evidence") or [] if e.get("quote")), None)
    steps = [_discovery_step(case)]
    for axis, label in (("action", "Czynność"), ("personalisation", "Personalizacja")):
        q = quote(axis)
        steps.append(_step(axis, label, "suspect" if q else "ok", f"„{q}”" if q else "Nie znaleziono cytatu na stronie"))
    if identity.get("licensed"):
        steps.append(_step("identity", "Uprawnienia", "refuted", identity.get("label") or "Podmiot z uprawnieniami w wykazie KNF"))
    else:
        steps.append(_step("identity", "Uprawnienia", "suspect" if identity.get("state") == "not_found" or not identity.get("matches") else "ok",
                           identity.get("label") or "Brak wpisu z zakresem doradztwa w przejrzanych wykazach"))
    second = case.get("secondOpinion") if isinstance(case.get("secondOpinion"), dict) else None
    if second and second.get("status") == "ready":
        steps.append(_step("secondOpinion", "Drugi głos (model)", "suspect" if second.get("needsReview") else "ok",
                           ("Rozbieżność z regułami: " if second.get("needsReview") else "Zgodny z regułami: ") + (second.get("quote") or second.get("verdict") or "")))
    steps.append(_decision(case))
    return steps


def proof_path(case):
    return {"M2": m2, "M3": m3}.get(case.get("module"), m1)(case)
