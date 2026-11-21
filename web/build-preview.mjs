import { build } from "esbuild";
import { copyFile } from "node:fs/promises";

await build({
  entryPoints: { preview: "src/preview.js" },
  outdir: "theme-preview",
  bundle: true,
  minify: true,
  format: "esm",
  target: ["chrome123", "firefox128", "safari17.5"],
  loader: { ".woff2": "file" },
  assetNames: "fonts/[name]-[hash]",
  legalComments: "linked",
  define: { "process.env.NODE_ENV": '"production"' },
});

await copyFile("src/preview.html", "theme-preview/index.html");

await copyFile(
  "node_modules/@astryxdesign/theme-neutral/fonts/figtree.LICENSE.txt",
  "theme-preview/fonts/figtree.LICENSE.txt",
);
