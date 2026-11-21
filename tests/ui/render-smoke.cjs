// Dependency-free smoke test of the React element tree and untrusted source text.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync("web/app.js", "utf8");
function render(data) {
  let first = true,
    output;
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
    ReactDOM: {
      createRoot() {
        return {
          render(v) {
            output = v;
          },
        };
      },
    },
    document: {
      getElementById() {
        return {};
      },
    },
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
  vm.runInNewContext(source, context);
  return output;
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
  "render smoke: empty state, React text, media, timed evidence and comparison OK",
);
