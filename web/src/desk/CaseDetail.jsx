import React, { useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Blockquote } from "@astryxdesign/core/Blockquote";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Divider } from "@astryxdesign/core/Divider";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Selector } from "@astryxdesign/core/Selector";
import { TextArea } from "@astryxdesign/core/TextArea";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { COVER_STATE, EVIDENCE_KIND, EVIDENCE_ROLE, HISTORY_KIND, MODALITY, MODULES, REL_STATUS, ROUTES, STATUS, clock, fmtDate, fmtDateTime, safeUrl } from "./labels.js";
import { ExternalLink, OriginToken, RecalcToken, ReReviewToken, SCALE_NOTE, disclosureText, discoveryLines, locatorText, reachText } from "./parts.jsx";

const STATUS_OPTIONS = [
  { value: "reviewing", label: "Przekaż do kontroli" },
  { value: "closed", label: "Zamknij: bez dalszych działań" },
  { value: "new", label: "Wróć do nowych" },
];

function Part({ title, children }) {
  return (
    <VStack gap={2}>
      <Heading level={3}>{title}</Heading>
      {children}
    </VStack>
  );
}

function Meta({ label, children }) {
  return <MetadataListItem label={label}>{children}</MetadataListItem>;
}

function Assessment({ c }) {
  const rel = c.relationship;
  return (
    <Part title="Dlaczego tutaj (ocena systemu)">
      {c.needsRecalc && !c.isV2 ? (
        <Text color="secondary">Ta wersja analizy nie ma oceny z bieżących reguł.{c.needsRecalcReason ? ` ${c.needsRecalcReason}.` : ""}</Text>
      ) : (
        <VStack gap={2}>
          <Text weight="semibold">{c.route === "refer" ? "Przesłanka do sprawdzenia" : ROUTES[c.route] || "Bez oceny"}</Text>
          {c.reason && <Text>{c.reason}</Text>}
          {c.reasons.length > 0 && (
            <List listStyle="disc" density="compact">
              {c.reasons.map((reason, i) => <Item key={i} marker="•" label={<Text>{reason}</Text>} />)}
            </List>
          )}
          <MetadataList>
            {c.requirement && <Meta label="Wymóg">{c.requirement.id ? `${c.requirement.id} · ` : ""}{c.requirement.label}{c.requirement.scope ? ` (${c.requirement.scope})` : ""}</Meta>}
            <Meta label="Siła przesłanki">
              {c.score?.value != null ? `${c.score.value} z 100 pkt (${({ strong: "mocna", moderate: "średnia", weak: "słaba" })[c.score.band] || "bez pasma"})` : `Brak podstaw do wyliczenia${c.score?.notComputableReason ? `: ${c.score.notComputableReason}` : ""}`}
            </Meta>
            <Meta label="Możliwe wyjaśnienie">{c.alternative || (c.route === "refer" ? "Nie podano możliwego wyjaśnienia" : "—")}</Meta>
            {c.ruleVersion && <Meta label="Reguły">{c.ruleVersion}{c.decidedBy ? ` · ${({ rules: "reguły", model: "model", "rules+model": "reguły i model" })[c.decidedBy] || c.decidedBy}` : ""}</Meta>}
            {rel && <Meta label="Relacja z firmą">{REL_STATUS[rel.status] || rel.status}{rel.basis ? ` (${rel.basis})` : ""}</Meta>}
          </MetadataList>
          <Text type="supporting" color="secondary">{SCALE_NOTE}</Text>
          {c.score?.components?.length > 0 && (
            <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Składniki punktacji</Text>}>
              <MetadataList>
                {c.score.components.map(([label, points], i) => <Meta key={i} label={label}>{points} pkt</Meta>)}
              </MetadataList>
            </Collapsible>
          )}
        </VStack>
      )}
      {c.summary && !c.isV2 && (
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Opis z poprzedniej wersji analizy</Text>}>
          <Text color="secondary">{c.summary}</Text>
        </Collapsible>
      )}
    </Part>
  );
}

function Facts({ c }) {
  const rel = c.relationship;
  const firm = rel?.firm;
  const candidates = firm?.candidates || [];
  return (
    <Part title="Fakty (bez oceny)">
      <MetadataList>
        {rel?.firmName && (
          <Meta label="Firma">
            {rel.firmName}
            {candidates.length > 0 ? `; wpisy w wykazie KNF: ${candidates.map((x) => `${x.name} (${x.registryId})`).join(", ")}` : ""}
            {firm?.identityStatus === "candidates" ? ". Operator do ustalenia." : ""}
          </Meta>
        )}
        {rel && <Meta label="Oznaczenie">{disclosureText(c)}</Meta>}
        <Meta label="Kanał">{c.creatorName || "—"}{c.creator?.status === "candidate" ? " (ID kanału do potwierdzenia)" : ""}</Meta>
        <Meta label="Zasięg">{reachText(c.reach || c.creator?.reach)}</Meta>
        <Meta label="Opublikowano">{fmtDate(c.publishedAt)}</Meta>
        <Meta label="Odczytano">{fmtDateTime(c.observedAt)}{c.firstScanId ? ` · skan ${c.firstScanId.slice(0, 8)}` : ""}</Meta>
        <Meta label="Droga odkrycia">
          {(c.discovery.length ? discoveryLines(c.discovery) : c.creator?.discoveries?.length ? discoveryLines(c.creator.discoveries) : [c.creator?.discoveredVia || "Droga odkrycia sprzed rozszerzenia kontraktu"]).join("; ")}
        </Meta>
      </MetadataList>
    </Part>
  );
}

function Proof({ c }) {
  const byId = new Map(c.evidence.map((e) => [e.id, e]));
  const shown = new Set();
  const rows = c.moments.map((m, i) => {
    const e = byId.get(m.evidenceId);
    shown.add(m.evidenceId);
    return { key: `m${i}`, label: m.label, start: m.start, link: safeUrl(m.deepLink) || e?.link, text: e?.text, locator: m.locator || e?.locator, role: e?.role, kind: e?.kind };
  });
  const rest = c.evidence.filter((e) => !shown.has(e.id) && e.role !== "context").slice(0, 8);
  const frames = c.evidence.filter((e) => e.kind === "frame");
  return (
    <Part title="Dowody i momenty">
      {rows.length === 0 && rest.length === 0 && <Text color="secondary">Brak wskazanego fragmentu dla tej sprawy.</Text>}
      {rows.map((r) => (
        <VStack key={r.key} gap={1}>
          <HStack gap={2} wrap="wrap" vAlign="center">
            {r.start != null ? <Token size="sm" color="blue" label={clock(r.start)} /> : <Token size="sm" color="gray" label="opis" />}
            <Text weight="semibold">{r.label}</Text>
          </HStack>
          {r.text && <Blockquote>{r.text}</Blockquote>}
          <HStack gap={3} wrap="wrap" vAlign="center">
            {r.start == null && r.locator && <Text type="supporting" color="secondary">Cytat {locatorText(r.locator)}</Text>}
            {r.link && <ExternalLink url={r.link}>{r.start != null ? `Otwórz w YouTube od ${clock(r.start)}` : "Otwórz źródło cytatu"}</ExternalLink>}
          </HStack>
        </VStack>
      ))}
      {rest.length > 0 && (
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Pozostałe dowody ({rest.length})</Text>}>
          <VStack gap={2} padding={2}>
            {rest.map((e, i) => (
              <VStack key={e.id || i} gap={0.5}>
                <Text type="supporting" color="secondary">{EVIDENCE_ROLE[e.role] || "fragment materiału"} · {EVIDENCE_KIND[e.kind] || e.kind}{e.start != null ? ` · ${clock(e.start)}` : ""}{e.caveat ? ` · ${e.caveat}` : ""}</Text>
                {e.text && <Text>{e.text}</Text>}
                {e.available ? <ExternalLink url={e.link}>Otwórz źródło</ExternalLink> : <Text type="supporting" color="secondary">{e.unavailableReason}</Text>}
              </VStack>
            ))}
          </VStack>
        </Collapsible>
      )}
      {frames.length > 0 && (
        <VStack gap={1}>
          <Text type="supporting" color="secondary">Kadry z momentów dowodu (obserwacja analityka kadrów, nie ocena)</Text>
          <HStack gap={2} wrap="wrap" vAlign="start">
            {frames.map((f) => (
              <VStack key={f.id} gap={0.5} width={176}>
                {f.thumbnailUrl && <Thumbnail src={f.thumbnailUrl} alt={f.text || "Kadr"} label={`Kadr z ${clock(f.start)}`} onClick={() => f.link && window.open(safeUrl(f.link), "_blank", "noopener")} />}
                <ExternalLink url={f.link}>Kadr z {clock(f.start)}</ExternalLink>
                <Text type="supporting" color="secondary" maxLines={3}>{f.text}</Text>
              </VStack>
            ))}
          </HStack>
        </VStack>
      )}
    </Part>
  );
}

function Scope({ c }) {
  const cov = c.coverage;
  const notChecked = c.relationship?.disclosure?.notChecked || [];
  return (
    <Part title="Kontrargumenty i zakres analizy">
      {c.counter.length > 0 ? (
        <VStack gap={1}>
          {c.counter.filter((e) => e.counterKind !== "neutral_context" && e.effect).slice(0, 4).map((e, i) => (
            <VStack key={e.id || i} gap={0.5}>
              {e.text && <Text>„{e.text}”</Text>}
              <Text type="supporting" color="secondary">{e.effect}</Text>
            </VStack>
          ))}
          <Text type="supporting" color="secondary">{c.counter.length} fragmentów rozważono jako kontekst lub kontrargument.</Text>
        </VStack>
      ) : (
        <Text color="secondary">{c.raw.counterEvidence ? "Nie znaleziono kontrargumentów w zbadanym zakresie." : "Nie zbadano kontrargumentów."}</Text>
      )}
      {!cov && <Text color="secondary">Zakres analizy nieznany. Każdy wniosek o braku oznaczenia dotyczy wyłącznie zbadanego opisu.</Text>}
      {cov?.legacyText && <Text color="secondary">Zakres (starsza analiza): {cov.legacyText}</Text>}
      {cov && !cov.legacyText && (
        <VStack gap={1}>
          <MetadataList>
            {Object.entries(cov.modalities).map(([key, m]) => {
              const bits = [COVER_STATE[m.state] || m.state];
              if (key === "description" && m.chars) bits.push(`${m.chars} znaków`);
              if (key === "transcript" && m.windows?.length) bits.push(`${clock(m.windows[0].start)}–${clock(m.windows[m.windows.length - 1].end)}`, m.source === "auto_captions" ? "auto-napisy YouTube" : m.source);
              if (key === "transcript" && m.reason) bits.push(m.reason);
              if (key === "frames" && m.moments?.length) bits.push(`momenty: ${m.moments.map(clock).join(", ")}`);
              if (key === "frames" && m.reason && m.state === "not_collected") bits.push(m.reason);
              if (key === "platformFlags") bits.push(m.paidPromotion == null ? "flagi nie sprawdzono" : m.paidPromotion ? "oznaczono płatną promocję" : "bez flagi płatnej promocji");
              return <Meta key={key} label={MODALITY[key] || key}>{bits.filter(Boolean).join(" · ")}</Meta>;
            })}
          </MetadataList>
          {cov.blocksConclusion && <Banner status="info" title="Wniosek o braku oznaczenia wstrzymany" description="Nie zbadano całego materiału, więc brak napisu nie oznacza, że oznaczenia nie ma." />}
          {notChecked.length > 0 && <Text type="supporting" color="secondary">Nie zbadano: {notChecked.map((m) => ({ transcript: "mowy", frames: "kadrów", platformFlags: "flagi płatnej promocji", description: "opisu" }[m] || m)).join(", ")}.</Text>}
        </VStack>
      )}
    </Part>
  );
}

function Decision({ c, onSaved }) {
  const [status, setStatus] = useState(null);
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(null);
  const [message, setMessage] = useState(null);
  const input = useRef(null);
  async function save() {
    if (busy) return;
    if (!note.trim()) {
      setInvalid(true);
      input.current?.focus();
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await api.decide(c, { status: status || (c.status === "new" ? "reviewing" : c.status), note: note.trim() });
      setNote("");
      setStatus(null);
      setConflict(null);
      setMessage("Decyzja została zapisana.");
      await onSaved();
    } catch (e) {
      if (e.status === 409) {
        setConflict(e.body?.current || true);
        await onSaved();
      } else setMessage(`Nie zapisano decyzji: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }
  const options = STATUS_OPTIONS.map((o) => (o.value === c.status ? { ...o, label: `${o.label} (bieżący stan)` } : o));
  return (
    <Part title="Decyzja">
      {c.lastDecision && <Text type="supporting" color="secondary">Ostatnia decyzja: {STATUS[c.lastDecision.status] || c.lastDecision.status}, {fmtDateTime(c.lastDecision.at)}. {c.lastDecision.note}</Text>}
      {conflict && <Banner status="warning" title="Sprawa zmieniła się podczas edycji" description="Pobrano bieżący stan i historię. Szkic uzasadnienia został zachowany; sprawdź zmiany i zapisz ponownie." />}
      <Selector label="Decyzja" value={status || (c.status === "new" ? "reviewing" : c.status)} options={options} onChange={setStatus} />
      <TextArea label="Uzasadnienie decyzji" ref={input} rows={3} htmlMaxLength={2000} value={note}
        onChange={(v) => { setNote(v); setInvalid(false); }}
        status={invalid ? { type: "error", message: "Wpisz uzasadnienie decyzji." } : undefined} />
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Button label="Zapisz decyzję" variant="primary" isLoading={busy} onClick={save} />
        {message && <Text as="p" role="status" type="supporting" color="secondary">{message}</Text>}
      </HStack>
      <Text type="supporting" color="secondary">System nie rozstrzyga o naruszeniu. Decyzja dotyczy tego, czy materiał kierujesz do dalszej kontroli.</Text>
    </Part>
  );
}

function describeHistory(h) {
  const kind = h.changeKind || (h.action === "capture" ? "content" : h.action);
  const d = h.details || {};
  const label = HISTORY_KIND[kind] || h.action;
  const extra = kind === "analysis" && (d.rulesFrom || d.scoreFrom != null) ? `: reguły ${d.rulesFrom ?? "?"} → ${d.rulesTo ?? "?"}${d.scoreFrom != null ? `, wynik ${d.scoreFrom} → ${d.scoreTo}` : ""}` : d.version && kind === "content" ? ` (wersja ${d.version})` : "";
  return { label: `${label}${extra}`, note: kind === "decision" ? h.note : kind === "content" ? "" : h.note };
}

function Chronicle({ c }) {
  const entries = [...c.history].reverse();
  return (
    <Part title="Historia wersji i decyzji">
      {entries.length === 0 ? <Text color="secondary">Brak wpisów w historii.</Text> : (
        <List density="compact" hasDividers>
          {entries.map((h, i) => {
            const x = describeHistory(h);
            return <Item key={h.seq ?? i} label={x.label} description={x.note || undefined} endContent={<Text type="supporting" color="secondary">{fmtDateTime(h.at)}</Text>} />;
          })}
        </List>
      )}
      {c.versions.length > 1 && <Text type="supporting" color="secondary">Wersji materiału: {c.versions.length}. Dowód z każdej wersji pobierzesz z historii przez API (/v1/cases/…/versions).</Text>}
    </Part>
  );
}

export function CaseDetail({ c, headingRef, onBack, onSaved }) {
  return (
    <VStack gap={4} padding={4}>
      <VStack gap={2}>
        <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
          <HStack gap={1} wrap="wrap" vAlign="center">
            <Token size="sm" color="gray" label={`${c.module} · ${MODULES[c.module] || ""}`} />
            <Token size="sm" color="gray" label={STATUS[c.status] || c.status} />
            <OriginToken origin={c.origin} />
            <RecalcToken c={c} />
            <ReReviewToken c={c} />
          </HStack>
          {onBack && <Button label="Wróć do listy" variant="ghost" size="sm" onClick={onBack} />}
        </HStack>
        <Heading level={2} ref={headingRef} tabIndex={-1}>{c.title}</Heading>
        <HStack gap={3} wrap="wrap" vAlign="center">
          <Text type="supporting" color="secondary">{[c.creatorName, c.platform, c.publishedAt && `opublikowano ${fmtDate(c.publishedAt)}`].filter(Boolean).join(" · ")}</Text>
          {c.url && <ExternalLink url={c.url}>Oryginał</ExternalLink>}
        </HStack>
      </VStack>
      {c.origin === "synthetic" || c.origin === "upload" ? (
        <Banner status="info" title={c.origin === "upload" ? "Plik operatora" : "Materiał syntetyczny z studia zespołu"} description="Nie pochodzi z bieżącego rynku. Nie wpływa na kolejki rzeczywistych materiałów." />
      ) : null}
      {c.needsRecalc && <Banner status="warning" title="Wynik ze starszej wersji analizy" description={`${c.needsRecalcReason ? `${c.needsRecalcReason}. ` : ""}Sekcja oceny wymaga przeliczenia. Fakty i dowody pozostają widoczne.`} />}
      <Assessment c={c} />
      <Divider />
      <Facts c={c} />
      <Divider />
      <Proof c={c} />
      <Divider />
      <Scope c={c} />
      <Divider />
      <Decision c={c} onSaved={onSaved} key={`${c.id}`} />
      <Divider />
      <Chronicle c={c} />
    </VStack>
  );
}
