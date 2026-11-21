// Wejście do testu renderowania po stronie serwera (bundlowane przez render-smoke.cjs, bez przeglądarki).
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Theme } from "@astryxdesign/core/theme";
import { themes, defaultThemeSlug } from "../../web/src/astryx-themes.js";
import { CaseDetail } from "../../web/src/desk/CaseDetail.jsx";
import { CaseList, OffersTable, RegisterTable } from "../../web/src/desk/Lists.jsx";
import { normalizeState } from "../../web/src/desk/model.js";
import { queueFromState, countsFromState } from "../../web/src/desk/adapter.js";
import { applyFilters, EMPTY_FILTERS } from "../../web/src/desk/filters.js";
import { safeUrl, timeLink } from "../../web/src/desk/labels.js";

const wrap = (node) => renderToStaticMarkup(<Theme theme={themes[defaultThemeSlug]} mode="light">{node}</Theme>);

export function run(rawState) {
  const state = normalizeState(rawState);
  const counts = countsFromState(state.cases);
  const review = queueFromState("review", state.cases);
  const register = queueFromState("adRegister", state.cases);
  const incomplete = queueFromState("incomplete", state.cases);
  const noop = () => {};
  return {
    counts,
    review: review.map((c) => c.id),
    register: register.map((c) => c.id),
    incomplete: incomplete.map((c) => c.id),
    demo: queueFromState("demo", state.cases).map((c) => c.id),
    m2: queueFromState("offersM2", state.cases).map((c) => c.id),
    filteredByModule: applyFilters(review, { ...EMPTY_FILTERS, module: "M2" }).length,
    detail: wrap(<CaseDetail c={review[0]} onSaved={noop} onBack={noop} />),
    reviewList: wrap(<CaseList items={review} tab="review" narrow={false} filters={EMPTY_FILTERS} onOpen={noop} emptyState={null} />),
    reviewListNarrow: wrap(<CaseList items={review} tab="review" narrow filters={EMPTY_FILTERS} onOpen={noop} emptyState={null} />),
    emptyList: wrap(<CaseList items={[]} tab="review" narrow={false} filters={EMPTY_FILTERS} onOpen={noop} emptyState={<p>PUSTO</p>} />),
    registerTable: wrap(<RegisterTable items={register} onOpen={noop} emptyState={null} />),
    offers: wrap(<OffersTable items={queueFromState("offersM2", state.cases)} module="M2" onOpen={noop} emptyState={null} />),
    legacyDetail: wrap(<CaseDetail c={incomplete.find((c) => c.needsRecalc)} onSaved={noop} onBack={null} />),
    unsafe: [safeUrl("javascript:alert(1)"), safeUrl("data:text/html,x"), safeUrl("https://example.com/a")],
    link: [timeLink("https://www.youtube.com/watch?v=abc", 125.9), timeLink("https://example.com/x", 5), timeLink("https://www.youtube.com/watch?v=abc", null)],
  };
}
