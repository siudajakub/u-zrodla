// Wejście do testu renderowania po stronie serwera (bundlowane przez render-smoke.cjs, bez przeglądarki).
// Dane: eksport prawdziwego API (web/sample/export.json), te same kształty co GET /v1/queues i /v1/cases.
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Theme } from "@astryxdesign/core/theme";
import { themes, defaultThemeSlug } from "../../web/src/astryx-themes.js";
import { CaseDetail } from "../../web/src/desk/CaseDetail.jsx";
import { CaseList, RegisterCounters, RegisterTable } from "../../web/src/desk/Lists.jsx";
import { Sources } from "../../web/src/desk/Sources.jsx";
import { normalizeCase, normalizeRow, normalizeState } from "../../web/src/desk/model.js";
import { queueQuery } from "../../web/src/desk/api.js";
import { EMPTY_FILTERS, queueFor } from "../../web/src/desk/filters.js";
import { parseHash } from "../../web/src/desk/route.js";
import { safeUrl, timeLink } from "../../web/src/desk/labels.js";

const wrap = (node) => renderToStaticMarkup(<Theme theme={themes[defaultThemeSlug]} mode="light">{node}</Theme>);

export function run(exported) {
  const state = normalizeState({ ...exported.state, findings: [] });
  const rows = (name) => exported.queues[name].map((i) => normalizeRow(i, state.creatorMap));
  const caseOf = (id) => normalizeCase(exported.cases[id], state.creatorMap);
  const review = rows("review");
  const register = rows("adRegister").filter((r) => exported.cases[r.id]);
  const noop = () => {};
  const aq = caseOf("youtube:AqXHkxDzSDI");
  const legacy = exported.queues.incomplete.find((i) => i.needsRecalc && i.module === "M1");
  return {
    counts: state.counts,
    review: review.map((c) => c.id),
    state,
    detail: wrap(<CaseDetail c={aq} onSaved={noop} onBack={noop} />),
    detailNarrow: wrap(<CaseDetail c={aq} onSaved={noop} onBack={noop} narrow />),
    detailRueo: wrap(<CaseDetail c={caseOf("youtube:7M0rC6-Rueo")} onSaved={noop} onBack={null} />),
    reviewList: wrap(<CaseList items={review} tab="review" narrow={false} filters={EMPTY_FILTERS} onOpen={noop} emptyState={null} />),
    reviewListNarrow: wrap(<CaseList items={review} tab="review" narrow filters={EMPTY_FILTERS} onOpen={noop} emptyState={null} />),
    emptyList: wrap(<CaseList items={[]} tab="review" narrow={false} filters={EMPTY_FILTERS} onOpen={noop} emptyState={<p>PUSTO</p>} />),
    registerTable: wrap(<RegisterTable items={register} filters={EMPTY_FILTERS} onOpen={noop} emptyState={null} />),
    offers: wrap(<CaseList items={rows("offersM2")} tab="review" kind="all" narrow={false} filters={{ ...EMPTY_FILTERS, state: "all", module: "M2" }} onOpen={noop} emptyState={null} />),
    counters: wrap(<RegisterCounters funnel={state.funnel} filters={EMPTY_FILTERS} update={() => noop} go={noop} />),
    funnel: state.funnel || null,
    queueFor: [queueFor("review", "all"), queueFor("incomplete", "M2"), queueFor("all", "M2"), queueFor("all", "M3"), queueFor("all", "all"), queueFor("closed", "all"), queueFor("demo", "all")],
    legacyHashes: ["#m2", "#m3", "#niepelne", "#incomplete", "#zamkniete", "#closed", "#demo", "#evidence", "#review", "#sources"].map((h) => { const r = parseHash(h); return [h, r.tab, r.filters.state, r.filters.module, r.add]; }),
    detailM2: wrap(<CaseDetail c={caseOf("web:noblesecurities.pl/klient-indywidualny/rachunek-ike")} onSaved={noop} onBack={null} />),
    detailM2Narrow: wrap(<CaseDetail c={caseOf("web:noblesecurities.pl/klient-indywidualny/rachunek-ike")} onSaved={noop} onBack={null} narrow />),
    detailM3: wrap(<CaseDetail c={caseOf("web:rdmwm.pl:m3")} onSaved={noop} onBack={null} />),
    detailM3Licensed: wrap(<CaseDetail c={caseOf("web:erste.pl:m3")} onSaved={noop} onBack={null} />),
    offersM3: wrap(<CaseList items={rows("offersM3")} tab="review" kind="all" narrow={false} filters={{ ...EMPTY_FILTERS, state: "all", module: "M3" }} onOpen={noop} emptyState={null} />),
    tiktokDetail: wrap(<CaseDetail c={caseOf(Object.keys(exported.cases).find((id) => id.startsWith("tiktok:")))} onSaved={noop} onBack={null} />),
    sources: wrap(<Sources data={state} busy={false} scanning={false} onScan={noop} rev={0} />),
    legacyDetail: legacy && exported.cases[legacy.id] ? wrap(<CaseDetail c={caseOf(legacy.id)} onSaved={noop} onBack={null} />) : null,
    query: queueQuery({ ...EMPTY_FILTERS, q: "xtb", module: "M1", band: "strong", source: "youtube", from: "2026-11-01", dateField: "publishedAt" }, { limit: 50, cursor: "50" }),
    unsafe: [safeUrl("javascript:alert(1)"), safeUrl("data:text/html,x"), safeUrl("https://example.com/a")],
    link: [timeLink("https://www.youtube.com/watch?v=abc", 125.9), timeLink("https://example.com/x", 5), timeLink("https://www.youtube.com/watch?v=abc", null)],
  };
}
