"""Convert validated Chromium measurements into bounded M2 observations."""
from math import hypot

OBS, UNKNOWN, OK = "obserwacja", "brak danych", "spełnione"
MIN_VISIBLE = 0.98
REFERENCE_CONTRAST = 4.5
EXPECTED_VIEWPORTS = 3
STATES = {
    "initial": "Po otwarciu",
    "claim": "Po przewinięciu do korzyści",
    "warning": "Po przewinięciu do ostrzeżenia",
    "expanded": "Po rozwinięciu",
    "identity": "Dane wydawcy",
    "profit": "Po przewinięciu do wzmianki o zysku",
}


def prominent(frame, key):
    item = frame.get(key)
    return bool(item and item["visibleFraction"] >= MIN_VISIBLE)


def box_distance(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return round(hypot(max(0, ax - bx - bw, bx - ax - aw), max(0, ay - by - bh, by - ay - ah)), 1)


def pixels(value):
    return float(value.removesuffix("px")) if value else None


def viewport_label(frame):
    return f"{frame['width']}×{frame['height']}"


def measure(frame, capture, focus):
    item = frame.get(focus)
    claim, warning, profit = frame.get("benefit"), frame.get("warning"), frame.get("profit")
    co_visible = prominent(frame, "benefit") and prominent(frame, "warning")
    return {
        "viewport": viewport_label(frame), "width": frame["width"], "height": frame["height"],
        "state": frame["state"], "stateLabel": STATES[frame["state"]],
        "px": item.get("px") if item else None, "bbox": item.get("bbox") if item else None,
        "inFrame": bool(item and item["visibleFraction"] > 0),
        "url": frame["url"], "domUrl": frame["domUrl"],
        "screenshotHash": frame["screenshotHash"], "domHash": frame["domHash"],
        "capturedAt": capture["observedAt"], "contentHash": capture["m2EvidenceRevision"],
        "scrollY": frame["scrollY"], "consentOverlay": frame["consentOverlay"],
        "benefit": claim, "warning": warning, "relation": frame.get("relation"),
        "rejectedWarning": frame.get("rejectedWarning"),
        "distancePx": box_distance(claim["documentBbox"], warning["documentBbox"]) if claim and warning else None,
        "sameFrame": co_visible, "profit": profit, "profitRelation": frame.get("profitRelation"),
        "profitDistancePx": box_distance(profit["documentBbox"], warning["documentBbox"]) if profit and warning else None,
        "dominantPx": (frame.get("warningDominant") or {}).get("px"),
        "focus": focus, "quote": item["text"] if item else None,
    }


def show_checks(capture, add):
    frames = capture["m2Views"]
    initial = [frame for frame in frames if frame["state"] == "initial"]
    one_per_size = {
        viewport_label(frame): frame for frame in frames if frame["warning"] and frame["warning"]["visibleFraction"] > 0
    }
    warnings = list(one_per_size.values())
    first_claim = next((frame for frame in frames if prominent(frame, "benefit")), initial[0])
    claim = first_claim["benefit"]
    warning_frames = [frame for frame in frames if frame["warning"]]
    same_creative = [frame for frame in warning_frames if frame["relation"] == "same_creative"]
    first_warning = next(iter(warnings or warning_frames), None)
    rejected = next((frame["rejectedWarning"] for frame in initial if frame["rejectedWarning"]), None)
    mode_auto = "automatyczny"
    mode_review = "wspomagany"
    mode_manual = "ręczny"

    def labeled_measurement(number, key):
        matching = [frame for frame in frames if prominent(frame, key)]
        if matching:
            first = matching[0]
            add(number, OK, first[key]["text"], mode_auto,
                measurements=[measure(first, capture, key)])
        else:
            add(number, UNKNOWN, "Brak jednoznacznego cytatu widocznego w zmierzonych stanach.",
                mode_manual, measurements=[measure(frame, capture, "benefit") for frame in initial])

    labeled_measurement("1", "legal")
    labeled_measurement("2", "label")
    matching = [frame for frame in frames if frame.get("profitRelation") == "same_creative" and
                prominent(frame, "profit") and prominent(frame, "warning")]
    profit_views = [frame for frame in frames if prominent(frame, "profit")]
    profit = next((frame["profit"] for frame in profit_views), None)
    measured = [
        measure(frame, capture, {"warning": "warning", "expanded": "warning", "profit": "profit"}.get(frame["state"], "benefit"))
        for frame in frames if frame["state"] != "identity"
    ]
    for frame in profit_views:
        if frame["state"] != "profit":
            measured.append(measure(frame, capture, "profit"))
    note = f"Korzyść promocyjna: „{claim['text'].rstrip('.')}”. "
    if profit:
        note += f"Twierdzenie o potencjalnym dochodzie: „{profit['text'].rstrip('.')}”. "
        if matching:
            note += "Wspólna sekcja i równoczesna widoczność na " + ", ".join(
                dict.fromkeys(map(viewport_label, matching))) + ". "
    else:
        note += "W przechwyconych stanach nie potwierdzono twierdzenia o potencjalnym zysku dla tego produktu. "
    if first_warning:
        note += f"Ostrzeżenie: „{first_warning['warning']['text'].rstrip('.')}”. "
        if profit and all(frame.get("profitRelation") != "same_creative" for frame in warning_frames):
            note += "Ostrzeżenie i twierdzenie o dochodzie znajdują się w osobnych elementach oferty. "
        elif not profit and not same_creative:
            note += "Ostrzeżenie i korzyść promocyjna znajdują się w osobnych elementach oferty. "
    else:
        note += "W przechwyconych fragmentach nie potwierdzono ostrzeżenia dotyczącego tej korzyści. "
    if rejected:
        note += f"Odrzucone powiązanie z innym produktem: „{rejected['text'].rstrip('.')}”. "
    both = len(set(map(viewport_label, matching))) == EXPECTED_VIEWPORTS
    add("3", OK if both else OBS if profit else UNKNOWN, note.strip(), mode_review, measurements=measured)

    standardized = [frame for frame in warnings if frame["relation"] == "same_creative"
                    and prominent(frame, "warning") and frame["warning"].get("px")
                    and (frame.get("warningDominant") or {}).get("px")]
    if standardized:
        smaller = any(pixels(frame["warning"]["px"]) < pixels(frame["warningDominant"]["px"]) for frame in standardized)
        complete = len(standardized) == EXPECTED_VIEWPORTS
        comparison = " · ".join(f"{viewport_label(frame)} {frame['warning']['px']} / {frame['warningDominant']['px']}"
                                for frame in standardized)
        add("4", OBS if smaller else OK if complete else UNKNOWN,
            "Rozmiar ostrzeżenia i dominujący rozmiar w tej samej sekcji. " + comparison +
            ". Dominanta według liczby widocznych znaków.", mode_auto,
            measurements=[measure(frame, capture, "warning") for frame in standardized])
    elif first_warning:
        add("4", UNKNOWN, "Brak wspólnej sekcji z wiarygodną dominantą dla korzyści i ostrzeżenia.",
            mode_manual, measurements=[measure(frame, capture, "warning") for frame in warnings or warning_frames])

    if first_warning:
        audience = capture.get("audience") or "nieustalony"
        quote = first_warning["warning"]["text"]
        add("9", UNKNOWN,
            f"Adresat materiału: {audience}. „{quote}” Analityk ocenia zrozumiałość ostrzeżenia dla tej grupy.",
            mode_manual, measurements=[measure(first_warning, capture, "warning")])
        low = [frame for frame in warnings if frame["warning"]["contrast"] is not None
               and frame["warning"]["contrast"] < REFERENCE_CONTRAST]
        all_visible = len(warnings) == EXPECTED_VIEWPORTS and all(prominent(frame, "warning") for frame in warnings)
        fully_measured = all_visible and all(frame["warning"]["contrast"] is not None for frame in warnings)
        initial_visible = all(prominent(frame, "warning") for frame in initial)
        summary = " · ".join(
            f'{viewport_label(frame)} {frame["warning"]["contrast"]}:1' if frame["warning"]["contrast"] is not None
            else f'{viewport_label(frame)} {frame["warning"]["contrastReason"]}' for frame in warnings
        )
        if not summary:
            summary = "Nie uzyskano widocznego fragmentu ostrzeżenia"
        layout = "Ostrzeżenie w pierwszym widoku. " if initial_visible else "Ostrzeżenie poza pierwszym widokiem na co najmniej jednym ekranie. "
        add("5", OBS if low or fully_measured and not initial_visible else OK if fully_measured else UNKNOWN,
            layout + summary + ". Wartość 4,5:1 stanowi pomocniczy próg czytelności.", mode_review,
            measurements=[measure(frame, capture, "warning") for frame in frames if frame in initial or frame["warning"]])

        roles = {frame["warning"]["role"] for frame in warnings}
        is_footer = bool(roles & {"footer", "footnote"})
        role_labels = {"body": "treść strony", "footer": "stopka", "footnote": "przypis", "header": "nagłówek"}
        role_summary = ", ".join(role_labels[role] for role in sorted(roles))
        add("6", OBS if is_footer else OK if all_visible else UNKNOWN,
            "Położenie elementu w DOM: " + (role_summary or "brak widocznego ostrzeżenia") + ".", mode_review,
            measurements=[measure(frame, capture, "warning") for frame in warnings or warning_frames])

        disclosed = [frame for frame in warnings if prominent(frame, "warning") and not frame["consentOverlay"]]
        expanded = any(frame["state"] == "expanded" for frame in disclosed)
        read_without_expanding = (len(disclosed) == EXPECTED_VIEWPORTS and not expanded
                                  and all(not frame.get("consentAction") for frame in disclosed))
        add("7", OBS if expanded else OK if read_without_expanding else UNKNOWN,
            "Ostrzeżenie odczytano po rozwinięciu elementu." if expanded else
            "Ostrzeżenie odczytano bez rozwijania. W razie potrzeby przewinięto stronę." if read_without_expanding else
            "Nie potwierdzono odczytu bez dodatkowej interakcji poza przewijaniem.",
            mode_auto, measurements=[measure(frame, capture, "warning") for frame in disclosed or warning_frames])

        sizes = " · ".join(f"{viewport_label(frame)} {frame['warning']['px'] or 'różne rozmiary'}, "
                           f"{round(frame['warning']['visibleFraction'] * 100)}% pola tekstu widoczne"
                           for frame in warnings)
        any_small = any((pixels(frame["warning"]["px"]) or 100) < 12 for frame in warnings)
        has_size = len(warnings) == EXPECTED_VIEWPORTS and all(frame["warning"]["px"] for frame in warnings)
        state = OBS if any_small or has_size and not all_visible else OK if has_size else UNKNOWN
        add("8", state, (sizes or "Brak porównywalnego widoku ostrzeżenia") +
            ". Próg 12 px jest pomocniczy. Udział widocznego pola to pomiar prostokątów tekstu.",
            mode_review, measurements=[measure(frame, capture, "warning") for frame in warnings or warning_frames])

        language = claim.get("language")
        warning_language = first_warning["warning"].get("language")
        if language and warning_language:
            add("10", UNKNOWN if language == warning_language else OBS,
                f"Język zadeklarowany w DOM dla korzyści: {language}. Dla ostrzeżenia: {warning_language}. "
                "Treść obu cytatów można zweryfikować w dowodzie.",
                mode_review, measurements=[measure(first_claim, capture, "benefit"), measure(first_warning, capture, "warning")])
    else:
        for number in ("4", "5", "6", "7", "8", "10"):
            add(number, UNKNOWN, "Pomiar wymaga potwierdzonego ostrzeżenia o reklamowanym produkcie.",
                mode_manual, measurements=[measure(frame, capture, "benefit") for frame in initial])


def marketing_review_suggestion(checks):
    """Use version-bound DOM proof to nominate a case for human review."""
    claim_check = next(check for check in checks if check["id"] == "3")
    measurements = claim_check.get("measurements", [])
    base = {"source": "rules", "criterionId": "3"}
    if not measurements:
        return {**base, "state": "unavailable", "reason": "Brak pomiaru Chromium dla tego materiału."}
    focus = [proof for proof in measurements if proof["focus"] == "profit" and proof["inFrame"]]
    candidate = next((proof for proof in focus if proof["width"] == 390), focus[0] if focus else None)
    if claim_check["state"] == OBS and candidate:
        warning = candidate["warning"]
        reason = ("Sprawdź, czy informacja o ryzyku bezpośrednio towarzyszy twierdzeniu o potencjalnym dochodzie."
                  if warning else "Sprawdź informację o ryzyku przy zarejestrowanym twierdzeniu o potencjalnym dochodzie.")
        return {
            **base, "state": "review", "reason": reason,
            "evidence": {
                "kind": "screenshot", "text": candidate["quote"], "url": candidate["url"],
                "domUrl": candidate["domUrl"], "sha256": candidate["screenshotHash"],
                "domSha256": candidate["domHash"], "contentHash": candidate["contentHash"],
            },
        }
    if claim_check["state"] == OK:
        return {**base, "state": "no_signal", "reason": "Oba fragmenty były widoczne razem w zmierzonych stanach."}
    return {**base, "state": "no_signal",
            "reason": "W zweryfikowanych fragmentach nie potwierdzono twierdzenia o potencjalnym zysku."}
