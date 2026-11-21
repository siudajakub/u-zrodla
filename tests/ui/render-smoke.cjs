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

// --- Główny pulpit Astryx (web/src/desk): kolejki z danych przykładowych i renderowanie szczegółu bez przeglądarki ---
const path = require("node:path");
const web = path.resolve("web");
const sample = path.join(web, "sample/state.json");
if (!fs.existsSync(sample)) {
  console.log("render smoke (pulpit Astryx): POMINIĘTO, brak web/sample/state.json (python3 web/sample/build_sample.py)");
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

assert.equal(desk.counts.review, 4, "cztery filmy w Co wymaga sprawdzenia");
assert.deepEqual(desk.review.map((id) => id.slice(8)).sort(), ["7M0rC6-Rueo", "AqXHkxDzSDI", "OIyPE0z2mng", "ZJrT-X08Xwc"]);
for (const id of ["youtube:xtMqKkFO-0M", "youtube:eQYmvRfHtr8", "youtube:ePfzHQVf-lc"])
  assert.ok(!desk.review.includes(id) && desk.register.includes(id), `jawna współpraca ${id} tylko w rejestrze`);
assert.ok(desk.demo.includes("demo-studio-aurora") && !desk.review.includes("demo-studio-aurora"), "syntetyczne tylko w demo");
assert.ok(desk.incomplete.length >= 3 && desk.incomplete.some((id) => id.startsWith("tiktok:")), "starsze rekordy w niepełnych danych");
assert.equal(desk.filteredByModule, 0, "filtr modułu bez wyników");
const detail = html(desk.detail);
for (const part of ["Dlaczego tutaj", "Fakty", "Dowody i momenty", "Kontrargumenty i zakres", "Decyzja", "Historia", "nie jest prawdopodobieństwem"])
  assert.ok(detail.includes(part) || detail.includes(part.replace("nie jest prawdopodobieństwem", "To nie jest prawdopodobieństwo")), `szczegół: ${part}`);
assert.match(detail, /link-pso\.xtb\.com/);
assert.match(detail, /Wróć do listy/);
assert.match(html(desk.reviewList), /100 z 100 pkt/);
assert.match(html(desk.reviewListNarrow), /Siła: mocna/);
assert.match(html(desk.emptyList), /PUSTO/);
assert.match(desk.registerTable, /youtube\.com\/watch\?v=[^"]+&amp;t=\d+s/);
assert.match(html(desk.registerTable), /w mowie/);
assert.match(html(desk.offers), /Kryteria z 19/);
assert.match(html(desk.legacyDetail), /Wynik ze starszej wersji analizy/);
assert.deepEqual(desk.unsafe, [null, null, "https://example.com/a"]);
assert.deepEqual(desk.link, ["https://www.youtube.com/watch?v=abc&t=125s", "https://example.com/x", "https://www.youtube.com/watch?v=abc"]);
assert.ok(!/<script/i.test(desk.detail));
console.log(`render smoke (pulpit Astryx): kolejki ${JSON.stringify(desk.counts)}, szczegół, lista, rejestr, M2 i starszy rekord OK`);
