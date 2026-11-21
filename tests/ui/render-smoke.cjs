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

assert.equal(desk.counts.review, 15, "piętnaście pozycji w Co wymaga sprawdzenia (cztery filmy, dziesięć stron firm, jedna oferta doradcza)");
assert.deepEqual(desk.review.filter((id) => id.startsWith("youtube:")).map((id) => id.slice(8)).sort(), ["7M0rC6-Rueo", "AqXHkxDzSDI", "OIyPE0z2mng", "ZJrT-X08Xwc"]);
assert.ok(desk.review.includes("web:rdmwm.pl:m3"));
assert.ok(desk.counts.adRegister > 200 && desk.counts.incomplete > 100, "liczniki z API (rejestr i niepełne)");
const detail = html(desk.detail);
for (const part of ["Dlaczego tutaj", "Momenty do sprawdzenia", "Co zbadano", "Firma", "Twórca i zasięg", "Decyzja", "Więcej: historia, punktacja, źródło, surowe dane", "Przekaż do kontroli", "Uzupełnij dane", "Bez sygnału", "Zamknij", "Tekst z obrazu nie jest odczytywany automatycznie"])
  assert.ok(detail.includes(part), `karta: ${part}`);
assert.match(detail, /TRADEXTB/);
assert.match(detail, /Wezwanie w mowie do linku w opisie/);
assert.match(desk.detail, /youtube\.com\/watch\?v=AqXHkxDzSDI&(amp;)?t=15s/);
assert.match(desk.detail, /\/v1\/frames\/AqXHkxDzSDI\//, "miniatury kadrów z API");
assert.ok(!/znaki \d+–\d+|\(znaki/.test(detail), "bez techniki „(znaki …)”");
assert.match(detail, /Wróć do listy/);
assert.ok(!/Momenty\s+Decyzja\s*$/.test(html(desk.detail)), "pasek telefonu tylko w widoku wąskim");
assert.match(html(desk.detailNarrow), /Momenty/);
assert.match(html(desk.detailRueo), /Pokaż wszystkie \(\d+\)/);
assert.match(html(desk.reviewList), /100 z 100 pkt/);
assert.match(html(desk.reviewListNarrow), /Siła: mocna/);
assert.match(html(desk.emptyList), /PUSTO/);
assert.match(html(desk.registerTable), /Firma\s+Platforma\s+Typ ujawnienia/);
assert.match(html(desk.registerTable), /oznaczona reklama|flaga płatnej promocji|w mowie/);
assert.match(html(desk.offers), /Strona\s+Firma\s+Przesłanka\s+Siła\s+Stan/);
assert.match(html(desk.reviewList), /Finfluencer/);
assert.match(html(desk.reviewList), /Reklama firmy/);
assert.match(html(desk.reviewList), /Doradztwo/);
const m2 = html(desk.detailM2);
for (const part of ["Otwórz stronę", "NOBLE Securities S.A. · dom maklerski", "Dlaczego tutaj", "Kryteria ryzyka", "8 z 19 wymaga uwagi", "Wszystkie 19 kryteriów wg stanu", "Co zbadano", "Baner cookies", "Firma", "Decyzja", "Rozmiar czcionki ryzyka"]) assert.ok(m2.includes(part), `karta M2: ${part}`);
assert.match(desk.detailM2, /\/evidence\/m2\/market\/[0-9a-f]{64}\.jpg/, "miniatury zrzutów M2");
assert.match(html(desk.detailM2Narrow), /Kryteria/);
const m3 = html(desk.detailM3);
for (const part of ["Otwórz ofertę", "rdmwm.pl", "Cztery cechy rekomendacji", "Czynność", "Personalizacja", "Instrument", "Rynek", "Kontrargument", "Uprawnienia", "Brak wpisu nie dowodzi braku uprawnień", "Przejrzane wykazy (12"]) assert.ok(m3.includes(part), `karta M3: ${part}`);
assert.match(html(desk.detailM3Licensed), /kontrola: podmiot uprawniony/);
assert.match(html(desk.offersM3), /kontrola: podmiot uprawniony/);
const tiktok = html(desk.tiktokDetail);
assert.match(tiktok, /Otwórz źródło/);
assert.ok(!/Otwórz w filmie/.test(tiktok), "TikTok: bez „Otwórz w filmie”");
assert.match(tiktok, /Zbadano tylko podpis/);
assert.match(tiktok, /data szacowana/);
assert.match(tiktok, /odtworzeń/);
const sources = html(desk.sources);
for (const part of ["Materiały i skierowania w czasie", "Skierowania do sprawdzenia", "Źródła: materiały per platforma", "YouTube", "TikTok", "Instagram", "Facebook", "WWW firm (M2)", "WWW doradców (M3)", "Biblioteka Reklam Meta", "dostęp zablokowany", "Meta Content Library", "import ręczny", "próbka z usługi zewnętrznej", "Wgraj zapisaną stronę Biblioteki Reklam Meta lub profilu Instagram", "Zapisz stronę"])
  assert.ok(sources.includes(part), `źródła: ${part}`);
assert.match(desk.sources, /data-chart="bar"|role="img"/);
if (desk.legacyDetail) assert.match(html(desk.legacyDetail), /starszej wersji analizy/);
assert.equal(desk.query, "limit=50&cursor=50&q=xtb&module=M1&platform=youtube&band=strong&dateField=publishedAt&since=2026-11-01T00%3A00%3A00%2B00%3A00");
assert.deepEqual(desk.unsafe, [null, null, "https://example.com/a"]);
assert.deepEqual(desk.link, ["https://www.youtube.com/watch?v=abc&t=125s", "https://example.com/x", "https://www.youtube.com/watch?v=abc"]);
assert.ok(!/<script/i.test(desk.detail));
console.log(`render smoke (pulpit Astryx): liczniki ${JSON.stringify(desk.counts)}, karta, lista, rejestr, M2 i zapytanie kolejki OK`);
