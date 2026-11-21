import React, { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Section } from "@astryxdesign/core/Section";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";

const metric = (value, unit = "") => value != null && value !== "" && Number.isFinite(Number(value))
  ? Number(value).toLocaleString("pl-PL", { maximumFractionDigits: 2 }) + unit : "brak danych";
const size = (element) => {
  if (!element?.bbox) return null;
  const box = element.bbox;
  const coordinates = Array.isArray(box) ? box : [box.left ?? box.x, box.top ?? box.y, box.width, box.height];
  return coordinates.every((value) => value != null) ? coordinates.map((value) => metric(value)).join(" × ") : null;
};
const fontSize = (value) => typeof value === "string" && /^\d+(?:\.\d+)?px$/.test(value)
  ? metric(Number.parseFloat(value), " px") : metric(value, " px");

function surroundingText(material, quote) {
  if (!material || !quote || material === quote) return null;
  const match = material.indexOf(quote);
  if (match === -1) return null;
  const start = Math.max(0, match - 250);
  const end = Math.min(material.length, match + quote.length + 250);
  return `${start > 0 ? "…" : ""}${material.slice(start, end)}${end < material.length ? "…" : ""}`;
}

export function createProof(shared) {
  const { list, text, date, status, clock, kindLabel, linkUrl, provenanceText, request } = shared;

  function Artifact({ url, children }) {
    const href = linkUrl(url);
    return href ? <Link href={href} target="_blank">{children}</Link> : null;
  }

  function ElementMeasure({ label, element }) {
    if (!element) return null;
    return (
      <VStack gap={0.5}>
        <Text weight="semibold">{label}</Text>
        {element.text && <Text>„{element.text}”</Text>}
        <Text type="supporting" color="secondary">
          Tekst {fontSize(element.px)} · kontrast {metric(element.contrast, " : 1")}
          {element.visibleFraction != null
            ? ` · w kadrze ${metric(element.visibleFraction * 100, "%")}`
            : element.inFrame === false ? " · poza kadrem" : element.inFrame === true ? " · w kadrze" : ""}
          {size(element) && ` · pozycja i rozmiar: ${size(element)} px`}
        </Text>
      </VStack>
    );
  }

  function Measurements({ checks }) {
    const measured = checks.find((check) => list(check.measurements).some((m) => m.warning && m.benefit))
      || checks.find((check) => list(check.measurements).length);
    const [active, setActive] = useState(undefined);
    const [preview, setPreview] = useState(null);
    const open = active === undefined ? measured?.id : active;
    return (
      <VStack gap={2}>
        <Heading level={3}>Kontrole materiału</Heading>
        {checks.map((check, index) => {
          const id = check.id ?? index;
          const measurements = list(check.measurements);
          return (
            <Section key={id} variant="transparent" dividers={["bottom"]} padding={0}>
              <Collapsible isOpen={open === id} onOpenChange={(isOpen) => { setActive(isOpen ? id : null); setPreview(null); }}
                trigger={<HStack gap={2} wrap="wrap" vAlign="center">
                  <Text weight="semibold">{check.label || check.id}</Text>
                  <Text type="supporting" color="secondary">{status(check.state)}</Text>
                </HStack>}>
                <VStack gap={2} padding={2}>
                  {check.evidence && <Text>{text(check.evidence)}</Text>}
                  {measurements.length ? measurements.map((item, index) => {
                    const view = item.viewport === "mobile" ? "Telefon" : item.viewport === "desktop" ? "Komputer" : text(item.viewport, "Widok");
                    return (
                      <Section variant="muted" padding={2} key={`${item.viewport}-${index}`}>
                        <VStack gap={1.5}>
                          <HStack wrap="wrap" gap={2} vAlign="center">
                            <Text weight="semibold">
                              {view}{item.stateLabel ? ` · ${item.stateLabel}` : ""}
                            </Text>
                            <Artifact url={item.url}>Zrzut · {view.toLowerCase()}</Artifact>
                            {linkUrl(item.url) && <Button size="sm" variant="ghost"
                              label={preview === item.url ? "Ukryj podgląd" : "Pokaż podgląd"}
                              onClick={() => setPreview(preview === item.url ? null : item.url)} />}
                            <Artifact url={item.domUrl}>Pomiary DOM · {view.toLowerCase()}</Artifact>
                          </HStack>
                          {preview === item.url && linkUrl(item.url) &&
                            <Artifact url={item.url}><img className="proof-image" src={linkUrl(item.url)} alt={`Zapis widoku: ${view.toLowerCase()}`} /></Artifact>}
                          {item.profit ? <ElementMeasure label="Twierdzenie o potencjalnym dochodzie" element={item.profit} />
                            : <ElementMeasure label="Komunikat o korzyści" element={item.benefit} />}
                          <ElementMeasure label={item.warning ? "Ostrzeżenie" : "Kandydat wykryty w archiwum"}
                            element={item.warning || (item.px != null ? item : null)} />
                          {(item.profitDistancePx ?? item.distancePx) != null &&
                            <Text type="supporting">Odstęp między komunikatem a ostrzeżeniem {metric(item.profitDistancePx ?? item.distancePx, " px")}</Text>}
                          {(item.capturedAt || item.state || item.screenshotHash || item.domHash || item.contentHash) &&
                            <details className="proof-meta">
                              <summary>Zapis dowodu</summary>
                              {item.capturedAt && <Text>Data pobrania: {date(item.capturedAt)}</Text>}
                              {item.state && <Text>Stan widoku: {item.state}</Text>}
                              {item.contentHash && <Text>SHA-256 treści: {item.contentHash}</Text>}
                              {item.screenshotHash && <Text>SHA-256 zrzutu: {item.screenshotHash}</Text>}
                              {item.domHash && <Text>SHA-256 DOM: {item.domHash}</Text>}
                            </details>}
                        </VStack>
                      </Section>
                    );
                  }) : <Artifact url={check.url}>Źródło kontroli</Artifact>}
                </VStack>
              </Collapsible>
            </Section>
          );
        })}
      </VStack>
    );
  }

  function Evidence({ finding, media }) {
    const [active, setActive] = useState(null);
    const evidence = list(finding.evidence);
    const checks = list(finding.checks);
    const comparison = finding.modalityComparison;
    const mediaUrl = linkUrl(finding.mediaUrl);
    const semantic = finding.semantic;
    const semanticAvailable = semantic?.status === "ready";
    const suggestion = finding.reviewSuggestion;
    const suggestedEvidence = suggestion?.evidence || semantic?.evidence;
    const modelQuote = suggestedEvidence?.text || semantic?.fragment;
    const context = suggestedEvidence?.context || suggestedEvidence?.paragraph ||
      (suggestedEvidence?.field === "description" ? surroundingText(finding.description, modelQuote) : null);
    const model = suggestion?.model || semantic?.model || finding.semanticModel;
    function jump(item) {
      if (!media.current) return;
      media.current.currentTime = Number(item.start);
      media.current.play().catch(() => {});
    }
    const Media = /\.(mp3|wav|m4a|aac|flac|ogg)(?:[?#]|$)/i.test(finding.mediaUrl) ? "audio" : "video";
    return (
      <VStack gap={3}>
        {comparison && <Section variant="muted" padding={2}>
          <HStack gap={3} wrap="wrap" vAlign="center">
            <Text type="supporting" weight="semibold">Priorytet po odsłuchu</Text>
            <Text type="supporting">Opis <strong>{comparison.descriptionOnly}</strong> → opis i mowa <strong>{comparison.withAudio}</strong> / 100</Text>
          </HStack>
        </Section>}
        {(suggestion || semanticAvailable) && <Section variant="muted" padding={2}>
          <VStack gap={1}>
            <Text weight="semibold">{suggestion?.state === "review"
              ? suggestion.source === "semantic" ? "Model wskazał materiał do sprawdzenia" : "Reguły wskazały materiał do sprawdzenia"
              : suggestion?.state === "uncertain" ? "Niejednoznaczny wynik"
              : suggestion?.state === "unavailable" ? "Brak wyniku wskazania"
              : suggestion?.state === "no_signal" ? "Brak sygnału do sprawdzenia"
              : `Sugestia modelu: ${text(semantic?.label)}`}</Text>
            {suggestion?.reason && <Text>{suggestion.reason}</Text>}
            {(model && (!suggestion || suggestion.source === "semantic")) && <Text type="supporting" color="secondary">
              {text(model)}{suggestion?.version || semantic?.version ? ` · ${suggestion?.version || semantic.version}` : ""}
              {semantic?.cosineSimilarity != null ? ` · podobieństwo ${metric(semantic.cosineSimilarity)}` : ""}
            </Text>}
            {suggestion?.source === "rules" && finding.rulesVersion &&
              <Text type="supporting" color="secondary">Wersja reguł: {finding.rulesVersion}</Text>}
            {modelQuote && <blockquote className="proof-quote"><Text>„{modelQuote}”</Text></blockquote>}
            {context && context !== modelQuote && <details className="proof-meta">
              <summary>Kontekst w zapisanym tekście</summary>
              <Text>{text(context)}</Text>
            </details>}
            <HStack gap={2} vAlign="center" wrap="wrap">
              {suggestedEvidence?.start != null && mediaUrl && <Button size="sm" variant="secondary"
                label={`Odtwórz sugestię · ${clock(suggestedEvidence.start)}`}
                onClick={() => jump(suggestedEvidence)} />}
              <Artifact url={suggestedEvidence?.url}>Źródło sugestii</Artifact>
            </HStack>
            {semantic?.ambiguity && <Text type="supporting">Wynik modelu jest niejednoznaczny. Sprawdź pełny materiał.</Text>}
          </VStack>
        </Section>}
        {mediaUrl && <Media ref={media} className="proof-player" aria-label="Nagranie źródłowe" src={mediaUrl} controls preload="metadata" />}
        {finding.module === "M2" && checks.length > 0 && <Measurements checks={checks} />}
        {!evidence.length && <Text color="secondary">Brak dostępnego fragmentu dowodowego.</Text>}
        {evidence.map((item, index) => (
          <Section key={`${item.kind}-${index}`} variant={active === index ? "muted" : "transparent"}
            dividers={["bottom"]} padding={2}>
            <VStack gap={1}>
              <HStack gap={2} wrap="wrap" vAlign="center">
                <Token label={kindLabel(item.kind)} size="sm" color="gray" />
                {item.start != null && mediaUrl && <Button size="sm" variant="secondary"
                  label={`Odtwórz ${clock(item.start)}${item.end == null ? "" : `–${clock(item.end)}`}`}
                  onClick={() => {
                    jump(item);
                    setActive(index);
                  }} />}
                {item.observedAt && <Text type="supporting" color="secondary">{date(item.observedAt)}</Text>}
              </HStack>
              {item.text && <blockquote className="proof-quote"><Text>„{item.text}”</Text></blockquote>}
              {(item.context || item.paragraph) && (item.context || item.paragraph) !== item.text &&
                <details className="proof-meta">
                  <summary>Akapit źródłowy</summary><Text>{text(item.context || item.paragraph)}</Text>
                </details>}
              <HStack gap={2} wrap="wrap">
                <Artifact url={item.url}>{item.kind === "screenshot" ? "Otwórz zrzut" : "Otwórz źródło cytatu"}</Artifact>
                <Artifact url={item.domUrl}>Otwórz pomiar DOM</Artifact>
              </HStack>
            </VStack>
          </Section>
        ))}
        {finding.module !== "M2" && checks.length > 0 && <Measurements checks={checks} />}
        <details className="proof-meta">
          <summary>Pochodzenie i zakres materiału</summary>
          <Text>{provenanceText(finding.provenance, finding.mode)}</Text>
          {finding.version && <Text>Wersja materiału: {finding.version}</Text>}
          {finding.rulesVersion && <Text>Wersja reguł: {finding.rulesVersion}</Text>}
          {finding.synthetic && <Text>Nagranie demonstracyjne</Text>}
          {finding.coverage && <Text>Zakres: {text(finding.coverage)}</Text>}
          {finding.module === "M3" && finding.description && <details className="proof-meta">
            <summary>Tekst pobrany ze źródła</summary>
            <Text>{finding.description}</Text>
          </details>}
          {finding.asrScope && <Text>Transkrypcja od {clock(finding.asrScope.start || 0)} do maks. {finding.asrScope.maxSeconds} s.</Text>}
          {finding.asrModel && <Text>Model transkrypcji: {text(finding.asrModel)}</Text>}
          {finding.semantic?.status === "unavailable" && <Text>Sugestia modelu podobieństwa jest niedostępna.</Text>}
        </details>
      </VStack>
    );
  }

  function HistoricalProof({ caseId, version }) {
    const [archive, setArchive] = useState(null);
    const [error, setError] = useState("");
    const media = React.useRef(null);
    return (
      <VStack gap={1}>
        {!archive && <HStack><Button size="sm" label={`Dowód z wersji ${version}`} clickAction={async () => {
          setError("");
          try {
            const result = await request(`/v1/cases/${encodeURIComponent(caseId)}/versions/${encodeURIComponent(version)}`);
            setArchive(result);
          } catch (failure) {
            setError(failure.message);
          }
        }} /></HStack>}
        {error && <Text role="alert">Nie można pobrać wersji: {error}</Text>}
        {archive && <VStack gap={1}>
          <Text weight="semibold">Zachowana wersja {archive.version} · {date(archive.observedAt)}</Text>
          <Text type="supporting" color="secondary">SHA-256: {archive.sha256}</Text>
          <Evidence finding={archive.finding} media={media} />
        </VStack>}
      </VStack>
    );
  }

  function History({ finding }) {
    const history = list(finding.history);
    return (
      <VStack gap={2}>
        <Heading level={3}>Historia sprawy</Heading>
        {history.length ? [...history].reverse().map((item, index) => (
          <Section key={item.id || index} variant="transparent" padding={2} dividers={["bottom"]}>
            <VStack gap={1}>
              <Text type="supporting" weight="semibold">{status(item.status || item.action)} · {date(item.at || item.createdAt)}</Text>
              {item.note && <Text>{item.note}</Text>}
              {item.action === "capture" && item.version != null && <HistoricalProof caseId={finding.id} version={item.version} />}
            </VStack>
          </Section>
        )) : <Text color="secondary">Brak wpisów w historii.</Text>}
      </VStack>
    );
  }
  return { Evidence, History };
}
