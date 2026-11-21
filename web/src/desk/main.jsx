import React from "react";
import { createRoot } from "react-dom/client";
import { InternationalizationProvider } from "@astryxdesign/core/i18n";
import polish from "@astryxdesign/core/locales/pl-PL.json";
import { Theme } from "@astryxdesign/core/theme";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import { themes, defaultThemeSlug } from "../astryx-themes.js";
import { Desk } from "./Desk.jsx";

createRoot(document.getElementById("app")).render(
  <Theme theme={themes[defaultThemeSlug]} mode="light">
    <InternationalizationProvider locale="pl-PL" messages={{ "pl-PL": polish }}>
      <Desk />
    </InternationalizationProvider>
  </Theme>,
);
