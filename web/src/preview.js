import React from "react";
import { createRoot } from "react-dom/client";
import { InternationalizationProvider } from "@astryxdesign/core/i18n";
import polish from "@astryxdesign/core/locales/pl-PL.json";
import { Theme } from "@astryxdesign/core/theme";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import { themes, defaultThemeSlug } from "./astryx-themes.js";
import { createDesk } from "../app.js";
import { createNeutralViews } from "./neutral-desk.jsx";
import "./preview.css";

const Desk = createDesk(React, createNeutralViews);
createRoot(document.getElementById("app")).render(
  React.createElement(
    Theme,
    { theme: themes[defaultThemeSlug], mode: "light" },
    React.createElement(InternationalizationProvider, { locale: "pl-PL", messages: { "pl-PL": polish } },
      React.createElement(Desk)),
  ),
);
