// Elementy wspólne kart spraw: kafelek, „Dlaczego tutaj”, zdanie drugiego głosu modelu, miniatury zrzutów z powiększeniem, „Decyzja”.
import React, { useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { TextArea } from "@astryxdesign/core/TextArea";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Lightbox } from "@astryxdesign/core/Lightbox";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { api, assetUrl } from "./api.js";
import { CHECK_STATE, RESOLUTIONS, viewLabel, RESOLUTION_LABEL, STATUS, fmtDateTime, fmtDay } from "./labels.js";

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
        <HStack key={i} gap={1.5} vAlign="start" role="listitem"><Text color="secondary">•</Text><Text maxLines={3}>{text}</Text></HStack>
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
      {alt && <Text type="supporting" color="secondary" maxLines={3}><Text weight="semibold" type="supporting">Możliwe wyjaśnienie: </Text>{alt.charAt(0).toLowerCase() + alt.slice(1)}</Text>}
    </Tile>
  );
}

/* Decyzja: cztery rodzaje, uzasadnienie i zapis w jednym bloku; ostatnia decyzja w jednej linii. */
export function DecisionTile({ c, onSaved }) {
  const [resolution, setResolution] = useState(null);
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState(null);
  const input = useRef(null);
  async function save() {
    if (busy) return;
    if (!resolution) {
      setInvalid("Wybierz rodzaj decyzji.");
      return;
    }
    if (!note.trim()) {
      setInvalid("Wpisz uzasadnienie decyzji.");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await api.decide(c, { resolution, note: note.trim() });
      setNote("");
      setResolution(null);
      setConflict(false);
      setMessage("Decyzja została zapisana.");
      await onSaved();
    } catch (e) {
      if (e.status === 409) {
        setConflict(true);
        await onSaved();
      } else setMessage(`Nie zapisano decyzji: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }
  const last = c.lastDecision;
  const lastLabel = last && (RESOLUTION_LABEL[last.resolution] || STATUS[last.status] || last.status);
  return (
    <Tile title="Decyzja" id="sekcja-decyzja" aside={last ? <Text type="supporting" color="secondary" maxLines={1}>Ostatnia: {lastLabel}, {fmtDateTime(last.at)}{last.note ? ` · ${last.note}` : ""}</Text> : undefined}>
      {conflict && <Banner status="warning" title="Sprawa zmieniła się podczas edycji" description="Pobrano bieżący stan. Szkic uzasadnienia zachowany; zapisz ponownie." />}
      <TextArea label="Uzasadnienie decyzji" isLabelHidden placeholder="Uzasadnienie decyzji (wymagane)" ref={input} rows={1} htmlMaxLength={2000} value={note}
        onChange={(v) => { setNote(v); setInvalid(null); }}
        status={invalid ? { type: "error", message: invalid } : undefined} />
      <HStack gap={1.5} wrap="wrap" vAlign="center">
        <HStack gap={1.5} wrap="wrap" role="group" aria-label="Rodzaj decyzji">
          {RESOLUTIONS.map((r) => (
            <Button key={r.value} label={r.label} size="sm" tooltip={r.hint} variant={resolution === r.value ? "primary" : "secondary"} aria-pressed={resolution === r.value} onClick={() => { setResolution(r.value); setInvalid(null); }} />
          ))}
        </HStack>
        <Button label="Zapisz decyzję" variant="primary" size="sm" isLoading={busy} onClick={save} />
        {message && <Text as="p" role="status" type="supporting" color="secondary">{message}</Text>}
      </HStack>
    </Tile>
  );
}
