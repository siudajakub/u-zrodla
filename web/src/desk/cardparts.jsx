// Elementy wspólne kart spraw: kafelek, „Dlaczego tutaj”, zdanie drugiego głosu modelu, miniatury zrzutów z powiększeniem, „Decyzja”.
import React, { useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { TextArea } from "@astryxdesign/core/TextArea";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Lightbox } from "@astryxdesign/core/Lightbox";
import { Link } from "@astryxdesign/core/Link";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { api, assetUrl } from "./api.js";
import { decisionDraft, hasOwnExplanation, needsOwnReason } from "./decision.js";
import { CHECK_STATE, RESOLUTIONS, viewLabel, RESOLUTION_LABEL, STATUS, fmtDateTime, fmtDay, safeUrl } from "./labels.js";

export function Tile({ title, id, children, aside }) {
  return (
    <Card padding={2} id={id}>
      <VStack gap={1.5}>
        <HStack gap={2} hAlign="between" vAlign="center">
          <Heading level={3}>{title}</Heading>
          {aside}
        </HStack>
        {children}
      </VStack>
    </Card>
  );
}

export function Bullets({ list }) {
  return (
    <VStack gap={1} role="list">
      {list.map((text, i) => (
        <HStack key={i} gap={1.5} vAlign="start" role="listitem"><Text color="secondary">•</Text><Text>{text}</Text></HStack>
      ))}
    </VStack>
  );
}

export function StateToken({ state }) {
  const [color, label] = CHECK_STATE[state] || ["gray", state || "—"];
  return <Token size="sm" color={color} label={label} />;
}

/** Miniatury zrzutów (komputer i telefon obok siebie); kliknięcie otwiera powiększenie w oknie. `shots`: [{ url, viewport }]. */
export function Shots({ shots, title }) {
  const [open, setOpen] = useState(null);
  const list = shots.map((s) => ({ ...s, src: assetUrl(s.url), label: viewLabel(s.viewport).replace(/ \d+×\d+$/, "") }));
  if (!list.length) return null;
  return (
    <>
      <HStack gap={1} vAlign="start">
        {list.map((s, i) => (
          <VStack key={s.url} gap={0.25} hAlign="center">
            <Thumbnail src={s.src} alt={`Zrzut strony: ${s.label}`} label={`zrzut strony, ${s.label}`} onClick={() => setOpen(i)} />
            <Text type="supporting" color="secondary">{s.label}</Text>
          </VStack>
        ))}
      </HStack>
      <Lightbox isOpen={open != null} onOpenChange={(v) => !v && setOpen(null)} index={open ?? 0} onIndexChange={setOpen} hasZoom
        media={list.map((s) => ({ src: s.src, alt: `${title || "Zrzut strony"}: ${s.label}`, caption: `${title ? `${title} · ` : ""}${s.label}` }))} />
    </>
  );
}

const MODEL_NAME = { "qwen/qwen3.8-27b": "Qwen3.8 27B", "google/gemma-4-31b-it": "Gemma 4 31B" };

/** Drugi głos modelu w jednej linii: „Model (Qwen3.8 27B, zapisany pomiar 21 lis): zgodny z regułami — „cytat””. Pole z API, bez własnej oceny. */
export function SecondOpinionLine({ c }) {
  const so = c.raw.secondOpinion;
  if (!so || so.status === "unavailable" || (!so.verdict && !so.quote && so.needsReview == null)) return null;
  const name = MODEL_NAME[so.modelId] || so.modelId || "model";
  const how = so.runtime === "local" ? "lokalnie" : so.runtime === "api" ? "pokaz przez API" : "zapisany pomiar";
  const when = so.measuredAt ? ` ${fmtDay(so.measuredAt)}` : "";
  const verdict = so.needsReview ? "rozbieżność — do przeglądu" : "zgodny z regułami";
  return (
    <Text type="supporting" data-testid="second-opinion">
      <Text weight="semibold" type="supporting">Model ({name}, {how}{when}): </Text>
      {verdict}{so.quote ? ` — „${so.quote}”` : ""}
    </Text>
  );
}

/* 1. Dlaczego tutaj: trzy punkty z API i jedna linia „Możliwe wyjaśnienie”. */
const ALT = /^Możliwe niewinne wyjaśnienie:?\s*/i;
export function WhyTile({ c }) {
  const clean = (t) => String(t).replace(/^Przesłanka do sprawdzenia:\s*/i, "").replace(/^./, (x) => x.toUpperCase());
  const reasons = c.reasons.filter((r) => !ALT.test(r)).map(clean);
  const alt = c.alternative || c.reasons.find((r) => ALT.test(r))?.replace(ALT, "") || null;
  const missing = c.route === "complete" && c.missing.length ? c.missing.map((m) => `Brakuje: ${m}.`) : null;
  const bullets = (missing || reasons).slice(0, 3);
  return (
    <Tile title="Dlaczego tutaj">
      {c.needsRecalc && !c.isV2 && !c.reason ? (
        <Text color="secondary">Wynik ze starszej wersji analizy. Przelicz materiały, aby zobaczyć uzasadnienie.</Text>
      ) : bullets.length ? <Bullets list={bullets} /> : <Text>{c.reason || "Brak uzasadnienia w tej wersji analizy."}</Text>}
      {c.counter.filter((e) => e.counterKind !== "neutral_context" && e.effect && e.text).slice(0, 2).map((e, i) => <Text key={e.id || i} type="supporting"><Text weight="semibold" type="supporting">Fragment do sprawdzenia: </Text>„{e.text}”. Sprawdź, czy dotyczy tej firmy i relacji. {safeUrl(e.link) && <Link href={safeUrl(e.link)} target="_blank">Otwórz źródło</Link>}</Text>)}
      {alt && <Text type="supporting" color="secondary" maxLines={3}><Text weight="semibold" type="supporting">Możliwe wyjaśnienie: </Text>{alt.charAt(0).toLowerCase() + alt.slice(1)}</Text>}
    </Tile>
  );
}

/* Propozycja pozostaje szkicem do chwili jawnego zatwierdzenia przez analityka. */
export function DecisionTile({ c, onSaved, onConflict, onPin }) {
  const [resolution, setResolution] = useState(null);
  const [note, setNote] = useState("");
  const [edited, setEdited] = useState(false);
  const [editedFor, setEditedFor] = useState(null);
  const [invalid, setInvalid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState(null);
  const input = useRef(null);
  const attempt = useRef(null);
  const baseline = useRef("");
  const choose = (value) => {
    if (resolution !== value) {
      attempt.current = null;
      const next = edited ? note : decisionDraft(c, value);
      baseline.current = next;
      setNote(next);
      setEditedFor(null);
    }
    setResolution(value);
    setInvalid(null);
  };
  const replaceDraft = () => {
    attempt.current = null;
    const next = decisionDraft(c, resolution);
    setNote(next);
    baseline.current = next;
    setEdited(false);
    setEditedFor(null);
    setInvalid(null);
  };
  async function save() {
    if (busy) return;
    if (!resolution) {
      setInvalid("Wybierz działanie przed zatwierdzeniem.");
      return;
    }
    if (needsOwnReason(c, resolution) && (editedFor !== resolution || !hasOwnExplanation(baseline.current, note))) {
      setInvalid("Podaj własnymi słowami powód, wynik lub otrzymane dane i ich źródło.");
      input.current?.focus();
      return;
    }
    if (!attempt.current && !RESOLUTIONS.some((r) => r.value === resolution && r.stages.includes(c.workflowStage || "review"))) {
      setInvalid("Etap sprawy zmienił się. Wybierz dostępne działanie.");
      return;
    }
    if (!note.trim()) {
      setInvalid("Uzupełnij uzasadnienie decyzji.");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setMessage(null);
    if (!attempt.current) {
      attempt.current = { resolution, note: note.trim(), requestId: globalThis.crypto?.randomUUID?.() || `decision-${Date.now()}-${Math.random().toString(36).slice(2)}`, expectedRevision: c.revision, reviewedVersion: c.version };
    }
    onPin?.(c.id);
    try {
      const result = await api.decide(c, attempt.current);
      setConflict(false);
      await onSaved({ result, resolution, caseId: c.id, title: c.title });
    } catch (e) {
      if (e.status === 409) {
        attempt.current = null;
        setConflict(true);
        await onConflict?.();
      } else if (e.status === 0 || e.status >= 500) setMessage(`Nie potwierdzono zapisu: ${e.message} Ponów bez zmiany treści, aby sprawdzić wynik.`);
      else { attempt.current = null; setMessage(`Nie zapisano decyzji: ${e.message}`); }
    } finally {
      setBusy(false);
    }
  }
  const last = c.lastDecision;
  const lastLabel = last && (RESOLUTION_LABEL[last.resolution] || STATUS[last.status] || last.status);
  return (
    <Tile title="Podejmij decyzję" id="sekcja-decyzja">
      {last && <VStack gap={0.5}><Text weight="semibold">Poprzednia zatwierdzona decyzja: {lastLabel} · {fmtDateTime(last.at)}</Text>{last.note && <Text>{last.note}</Text>}</VStack>}
      {conflict && <Banner status="warning" title="Sprawa zmieniła się podczas edycji" description="Pobrano bieżący stan. Twój szkic został zachowany. Sprawdź go i zatwierdź ponownie." />}
      <Text weight="semibold">1. Wybierz dalsze działanie</Text>
      <VStack gap={1} role="group" aria-label="Dalsze działanie">
        {RESOLUTIONS.filter((r) => r.stages.includes(c.workflowStage || "review")).map((r) => (
          <HStack key={r.value} gap={2} vAlign="center" wrap="wrap">
            <Button label={r.label} variant={resolution === r.value ? "primary" : "secondary"} aria-pressed={resolution === r.value} onClick={() => choose(r.value)} />
            <Text type="supporting">{r.hint}</Text>
          </HStack>
        ))}
      </VStack>
      {resolution && <VStack gap={1}>
        <Text weight="semibold">2. Sprawdź i uzupełnij uzasadnienie</Text>
        <Text type="supporting" color="secondary">Propozycja robocza z danych i reguł, bez dodatkowego modelu językowego. Sprawdź ją względem dowodów i zmień przed zatwierdzeniem.</Text>
        {edited && <HStack gap={1} wrap="wrap" vAlign="center"><Text type="supporting">Twoja edycja jest zachowana po zmianie działania.</Text><Button label="Zastąp tekst nową propozycją" variant="ghost" onClick={replaceDraft} /></HStack>}
        <TextArea label="Uzasadnienie decyzji" ref={input} rows={5} htmlMaxLength={2000} value={note} onChange={(v) => { attempt.current = null; setNote(v); setEdited(true); setEditedFor(resolution); setInvalid(null); }} status={invalid ? { type: "error", message: invalid } : undefined} />
        <HStack gap={2} wrap="wrap" vAlign="center"><Button label="Zatwierdź i zapisz decyzję" variant="primary" size="lg" style={{ minHeight: "2.75rem" }} isLoading={busy} onClick={save} />{message && <Text role="status">{message}</Text>}</HStack>
      </VStack>}
      {!resolution && invalid && <Text role="alert">{invalid}</Text>}
    </Tile>
  );
}
