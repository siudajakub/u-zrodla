// Dependency-free smoke test of the React element tree and untrusted source text.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync("web/app.js", "utf8").replace("export function", "function");
function render(data) {
  let first = true;
  const React = {
    Fragment: Symbol("fragment"),
    createElement(type, props, ...children) {
      if (typeof type === "function")
        return type({
          ...props,
          children: children.length === 1 ? children[0] : children,
        });
      return { type, props: props || {}, children: children.flat(Infinity) };
    },
    useState(initial) {
      if (first) {
        first = false;
        return [data, () => {}];
      }
      return [initial, () => {}];
    },
    useRef(value) {
      return { current: value };
    },
    useEffect() {},
    useCallback(fn) {
      return fn;
    },
  };
  const context = {
    React,
    location: {
      origin: "http://localhost",
      protocol: "http:",
      host: "localhost",
    },
    URL,
    URLSearchParams,
    setTimeout,
    clearTimeout,
    console,
  };
  return vm.runInNewContext(`${source}\nReact.createElement(createDesk(React));`, context);
}
function nodes(tree) {
  if (tree == null || typeof tree !== "object") return [];
  return [tree, ...(tree.children || []).flatMap(nodes)];
}
function allText(tree) {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  return (tree.children || []).map(allText).join(" ");
}
const empty = render({ findings: [], creators: [], sources: [], scans: [] });
assert.match(allText(empty), /Brak materiałów dla wybranych filtrów/);
const populated = render({
  creators: [{ id: "c", name: "Autor", platform: "YouTube" }],
  sources: [],
  scans: [],
  findings: [
    {
      id: "demo-studio-aurora",
      synthetic: true,
      creatorId: "c",
      title: "<script>alert(1)</script>",
      module: "M1",
      platform: "YouTube",
      score: 75,
      summary: "Materiał",
      mediaUrl: "/media/studio.mp4",
      evidence: [{ kind: "audio", start: 7, text: "Partnerstwo" }],
      status: "new",
      modalityComparison: { descriptionOnly: 12, withAudio: 75 },
    },
  ],
});
const elements = nodes(populated);
assert.match(allText(populated), /<script>alert\(1\)<\/script>/); // React renders this as text, not HTML.
assert.ok(!elements.some((el) => el.props?.dangerouslySetInnerHTML));
assert.ok(elements.some((el) => el.type === "video"));
assert.ok(
  elements.some((el) => el.type === "button" && allText(el).includes("0:07")),
);
assert.match(allText(populated), /Sam opis/);
assert.match(allText(populated), /Otwórz przykład z nagrania/);
assert.match(allText(populated), /Autor/);
console.log(
  "render smoke (stary pulpit /legacy.html): empty state, React text, media, timed evidence and comparison OK",
);

// --- Główny pulpit Astryx (web/src/desk): kolejki i karty z eksportu prawdziwego API, renderowanie bez przeglądarki ---
const path = require("node:path");
const web = path.resolve("web");
const sample = path.join(web, "sample/export.json");
if (!fs.existsSync(sample)) {
  console.log("render smoke (pulpit Astryx): POMINIĘTO, brak web/sample/export.json (python3 web/sample/build_sample.py)");
  process.exit(0);
}
const { buildSync } = require(path.join(web, "node_modules/esbuild"));
const out = path.join(require("node:os").tmpdir(), `desk-ssr-${process.pid}.cjs`);
buildSync({
  entryPoints: [path.resolve("tests/ui/desk-ssr-entry.jsx")],
  bundle: true,
  platform: "node",
  format: "cjs",
  outfile: out,
  nodePaths: [path.join(web, "node_modules")],
  loader: { ".woff2": "empty", ".css": "empty" },
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "error",
});
const desk = require(out).run(JSON.parse(fs.readFileSync(sample, "utf8")));
fs.rmSync(out, { force: true });
const html = (markup) => markup.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

assert.equal(desk.counts.review, 14, "czternaście pozycji w Do sprawdzenia (cztery filmy, dziewięć stron firm, jedna oferta doradcza)");
assert.deepEqual(desk.review.filter((id) => id.startsWith("youtube:")).map((id) => id.slice(8)).sort(), ["7M0rC6-Rueo", "AqXHkxDzSDI", "OIyPE0z2mng", "ZJrT-X08Xwc"]);
assert.ok(desk.review.includes("web:rdmwm.pl:m3"));
assert.ok(desk.counts.adRegister > 200 && desk.counts.incomplete > 100, "liczniki z API (rejestr i niepełne)");
const detail = html(desk.detail);
for (const part of ["Dlaczego tutaj", "Dowód", "Podejmij decyzję", "Dokumentacja i historia", "Możliwe wyjaśnienie", "Materiały twórców"])
  assert.ok(detail.includes(part), `karta: ${part}`);
for (const gone of ["Co zbadano", "Twórca i zasięg", "Momenty do sprawdzenia", "Bez sygnału", "Surowe dane", "Tekst z obrazu nie jest odczytywany", "Pokaż wszystkie"])
  assert.ok(!detail.includes(gone), `karta bez: ${gone}`);
assert.match(detail, /TRADEXTB/);
assert.match(desk.detail, /youtube\.com\/watch\?v=AqXHkxDzSDI&(amp;)?t=15s/);
assert.match(desk.detail, /Dokumentacja i historia/, "dokumentacja w osobnym widoku");
assert.ok(!/znaki \d+–\d+|\(znaki/.test(detail), "bez techniki „(znaki …)”");
assert.match(detail, /Wróć do listy/);
assert.match(html(desk.detailNarrow), /Dowód\s+Decyzja/, "stopka telefonu: Dowód i Decyzja");
assert.ok(!/Dowód\s+Decyzja\s*$/.test(detail), "pasek telefonu tylko w widoku wąskim");
assert.doesNotMatch(html(desk.reviewList), /mocna 100/);
assert.doesNotMatch(html(desk.reviewListNarrow), /mocna 100/);
assert.match(html(desk.emptyList), /PUSTO/);
assert.match(html(desk.registerTable), /Materiał\s+Firma\s+Jak ujawniono/);
assert.match(html(desk.registerTable), /w opisie|flaga YouTube|w mowie/);
assert.ok(!/Platforma\s+Typ ujawnienia/.test(html(desk.registerTable)), "rejestr bez kolumny Platforma");
assert.match(html(desk.offers), /Materiał\s+Firma\s+Powód/);
assert.match(html(desk.reviewList), /Materiały twórców/);
assert.match(html(desk.reviewList), /Reklamy firm/);
assert.match(html(desk.reviewList), /Oferty doradztwa/);
assert.ok(!/Finfluencer|Reklama firmy/.test(html(desk.reviewList)), "jedna nazwa modułu ze słownika");
assert.deepEqual(desk.queueFor, ["review", "incomplete", "offersM2", "offersM3", "all", "closed", "demo"], "filtr Stan mapuje się na kolejki API");
assert.deepEqual(desk.legacyHashes.map((x) => x.join("|")), ["#m2|review|all|M2|false", "#m3|review|all|M3|false", "#niepelne|review|incomplete|all|false", "#incomplete|review|incomplete|all|false", "#zamkniete|review|closed|all|false", "#closed|review|closed|all|false", "#demo|review|demo|all|false", "#evidence|sources|review|all|true", "#review|review|review|all|false", "#sources|sources|review|all|false"], "stare adresy przekierowują na filtr");
if (desk.funnel?.explainedAutomatically) assert.match(html(desk.counters), /w mowie \d+/, "liczniki rejestru z funnel");
const m2 = html(desk.detailM2);
for (const part of ["Otwórz stronę", "NOBLE Securities S.A. · dom maklerski", "Dlaczego tutaj i dowód", "Informacja o ryzyku przy zysku", "Dokumentacja i historia", "Podejmij decyzję"]) assert.ok(m2.includes(part), `karta M2: ${part}`);
for (const gone of ["Kryteria ryzyka", "Baner cookies", "Co zbadano", "Wynik reguł", "próg skierowania"]) assert.ok(!m2.includes(gone), `karta M2 bez: ${gone}`);
assert.match(desk.detailM2, /\/evidence\/m2\/market\/[0-9a-f]{64}\.jpg/, "miniatury zrzutów M2");
assert.ok(!/ px dalej \(próg|y=\d/.test(m2), "M2 bez surowych pomiarów w zdaniu: " + (m2.match(/.{40}(?: px dalej \(próg|y=\d).{30}/) || [""])[0]);
assert.match(html(desk.detailM2Narrow), /Dowód\s+Decyzja/);
const m3 = html(desk.detailM3);
for (const part of ["Otwórz ofertę", "rdmwm.pl", "Dowód", "Czynność", "Personalizacja", "Instrument", "Rynek", ]) assert.ok(m3.includes(part), `karta M3: ${part}`);
for (const gone of ["Cztery cechy rekomendacji", "Co zbadano", "Przejrzane wykazy (12"]) assert.ok(!m3.includes(gone), `karta M3 bez: ${gone}`);
assert.match(html(desk.detailM3Licensed), /Phinance|Erste|uprawniony/);
assert.match(html(desk.offersM3), /kontrola: podmiot uprawniony/);
const tiktok = html(desk.tiktokDetail);
assert.match(tiktok, /Otwórz źródło/);
assert.ok(!/Otwórz w filmie/.test(tiktok), "TikTok: bez „Otwórz w filmie”");
assert.match(tiktok, /Mowa/);
assert.match(tiktok, /Niepełne|niedostępn|nie zbadano/i);
const sources = html(desk.sources);
for (const part of ["Materiały i skierowania w czasie", "Skierowania do sprawdzenia", "Platformy", "YouTube", "TikTok", "Instagram", "Facebook", "Strony firm", "Strony doradców", "Biblioteka Reklam Meta", "Droga odczytu", "Następny krok", "Dodaj materiał", "Skanuj na żywo"])
  assert.ok(sources.includes(part), `źródła: ${part}`);
for (const gone of ["Źródła: materiały per platforma", "meta.token", "docs/lanes", "/v1/import/meta"]) assert.ok(!sources.includes(gone), `źródła bez: ${gone}`);
if (desk.state.models) assert.ok(sources.includes("Modele") && /Qwen|multilingual-e5/.test(sources), "kafel Modele");
assert.match(desk.sources, /data-chart="bar"|role="img"/);
if (desk.legacyDetail) assert.match(html(desk.legacyDetail), /starszej wersji analizy/);
assert.equal(desk.query, "limit=50&cursor=50&q=xtb&module=M1&platform=youtube&dateField=publishedAt&since=2026-11-01T00%3A00%3A00%2B00%3A00");
assert.deepEqual(desk.unsafe, [null, null, "https://example.com/a"]);
assert.deepEqual(desk.link, ["https://www.youtube.com/watch?v=abc&t=125s", "https://example.com/x", "https://www.youtube.com/watch?v=abc"]);
assert.ok(!/<script/i.test(desk.detail));
console.log(`render smoke (pulpit Astryx): liczniki ${JSON.stringify(desk.counts)}, karta, lista, rejestr, M2 i zapytanie kolejki OK`);
