// Elementy wspólne kart spraw: kafelek, punkty, plakietka stanu, miniatury zrzutów z powiększeniem.
import React, { useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { TextArea } from "@astryxdesign/core/TextArea";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Lightbox } from "@astryxdesign/core/Lightbox";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { api, assetUrl } from "./api.js";
import { CHECK_STATE, RESOLUTIONS, viewLabel, RESOLUTION_LABEL, ROUTES, STATUS, fmtDateTime } from "./labels.js";

export function Tile({ title, id, children, aside }) {
  return (
    <Card padding={3} id={id}>
      <VStack gap={2}>
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
    <VStack gap={1.5} role="list">
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
export function Shots({ shots, title, size = 64 }) {
  const [open, setOpen] = useState(null);
  const list = shots.map((s) => ({ ...s, src: assetUrl(s.url), label: viewLabel(s.viewport).replace(/ \d+×\d+$/, "") }));
  if (!list.length) return null;
  return (
    <>
      <HStack gap={1.5} vAlign="start">
        {list.map((s, i) => (
          <VStack key={s.url} gap={0.5} hAlign="center">
            <Thumbnail src={s.src} alt={`Zrzut strony: ${s.label}`} label={`zrzut strony, ${s.label}`} style={{ width: s.viewport?.startsWith("phone") ? Math.round(size * 0.7) : Math.round(size * 1.6), height: size }} onClick={() => setOpen(i)} />
            <Text type="supporting" color="secondary">{s.label}</Text>
          </VStack>
        ))}
      </HStack>
      <Lightbox isOpen={open != null} onOpenChange={(v) => !v && setOpen(null)} index={open ?? 0} onIndexChange={setOpen} hasZoom
        media={list.map((s) => ({ src: s.src, alt: `${title || "Zrzut strony"}: ${s.label}`, caption: `${title ? `${title} · ` : ""}${s.label}` }))} />
    </>
  );
}

/* Dlaczego tutaj: maksymalnie trzy punkty z API, reszta pod „pokaż wszystkie”. */
/* 1. Dlaczego tutaj: maksymalnie trzy punkty z API, reszta pod „pokaż wszystkie”. */
export function WhyTile({ c }) {
  const reasons = c.reasons;
  const lead = reasons.slice(0, 3);
  const rest = reasons.slice(3);
  const bullets = (list) => (
    <VStack gap={1.5} role="list">
      {list.map((text, i) => (
        <HStack key={i} gap={1.5} vAlign="start" role="listitem"><Text color="secondary">•</Text><Text>{text}</Text></HStack>
      ))}
    </VStack>
  );
  return (
    <Tile title="Dlaczego tutaj" aside={c.route === "refer" ? <Token size="sm" color="blue" label="do sprawdzenia" /> : <Token size="sm" color="gray" label={ROUTES[c.route] || c.route || "bez oceny"} />}>
      {c.needsRecalc && !c.isV2 && !c.reason ? (
        <Text color="secondary">Wynik ze starszej wersji analizy. Przelicz materiały, aby zobaczyć uzasadnienie.</Text>
      ) : reasons.length ? (
        <>
          {bullets(lead)}
          {rest.length > 0 && <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Pokaż wszystkie ({reasons.length})</Text>}>{bullets(rest)}</Collapsible>}
        </>
      ) : <Text>{c.reason || "Brak uzasadnienia w tej wersji analizy."}</Text>}
    </Tile>
  );
}

/* Decyzja: cztery rodzaje, notatka, ostatnia decyzja w jednym wierszu. */
/* 6. Decyzja: cztery rodzaje, notatka, ostatnia decyzja w jednym wierszu. */
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
  const chosen = RESOLUTIONS.find((r) => r.value === resolution);
  return (
    <Tile title="Decyzja" id="sekcja-decyzja">
      {last && <Text type="supporting" color="secondary">Ostatnia: {lastLabel}, {fmtDateTime(last.at)}{last.note ? ` · ${last.note}` : ""}</Text>}
      {conflict && <Banner status="warning" title="Sprawa zmieniła się podczas edycji" description="Pobrano bieżący stan. Szkic uzasadnienia zachowany; zapisz ponownie." />}
      <HStack gap={2} wrap="wrap" role="group" aria-label="Rodzaj decyzji">
        {RESOLUTIONS.map((r) => (
          <Button key={r.value} label={r.label} size="sm" variant={resolution === r.value ? "primary" : "secondary"} aria-pressed={resolution === r.value} onClick={() => { setResolution(r.value); setInvalid(null); }} />
        ))}
      </HStack>
      <Text type="supporting" color="secondary">{chosen ? chosen.hint : "Wybierz rodzaj decyzji."}</Text>
      <TextArea label="Uzasadnienie decyzji" ref={input} rows={2} htmlMaxLength={2000} value={note}
        onChange={(v) => { setNote(v); setInvalid(null); }}
        status={invalid ? { type: "error", message: invalid } : undefined} />
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Button label="Zapisz decyzję" variant="primary" isLoading={busy} onClick={save} />
        {message && <Text as="p" role="status" type="supporting" color="secondary">{message}</Text>}
      </HStack>
      <Text type="supporting" color="secondary">System nie rozstrzyga o naruszeniu; to Ty decydujesz, czy kierujesz materiał do kontroli.</Text>
    </Tile>
  );
}
