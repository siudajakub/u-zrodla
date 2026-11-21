/* Offline analyst desk; React is served locally from vendor/. */
(() => {
  const h = React.createElement;
  const { useState, useEffect, useRef, useCallback } = React;
  const list = (value) => (Array.isArray(value) ? value : []);
  const text = (value, fallback = "Brak danych") =>
    value == null || value === ""
      ? fallback
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
  const date = (value) => {
    if (!value) return "Brak danych";
    const d = new Date(value);
    return isNaN(d)
      ? String(value)
      : d.toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: "short" });
  };
  const labels = {
    new: "Nowa",
    reviewing: "W analizie",
    closed: "Zamknięta",
    ok: "Dostępne",
    success: "Zakończono",
    done: "Zakończono",
    failed: "Błąd",
    error: "Błąd",
    pending: "Oczekuje",
    queued: "W kolejce",
    running: "W toku",
    partial: "Częściowy wynik",
    unavailable: "Niedostępne",
    stale: "Nieaktualne",
    forbidden: "Odmowa dostępu",
    rate_limited: "Limit zapytań",
    capture: "Zachowano materiał",
    decision: "Decyzja",
    contract: "Porównanie umowy",
  };
  const status = (value) => labels[value] || text(value);
  const kindLabel = (value) =>
    ({
      audio: "Mowa",
      description: "Opis",
      screenshot: "Zrzut strony",
      registry: "Rejestr",
    })[value] || text(value, "Fragment materiału");
  const modeLabel = (value) =>
    ({
      replay: "odtworzenie",
      live: "na żywo",
      upload: "plik operatora",
      import: "import",
    })[value] || text(value);
  const clock = (seconds) =>
    `${Math.floor(Number(seconds) / 60)}:${String(
      Math.floor(Number(seconds) % 60),
    ).padStart(2, "0")}`;
  const linkUrl = (value) => {
    if (!value) return "";
    try {
      const u = new URL(value, location.origin);
      return ["http:", "https:"].includes(u.protocol) ? u.href : "";
    } catch {
      return "";
    }
  };
  const El = (tag, props, ...children) => h(tag, props, ...children.flat());
  const Button = ({ children, primary, ...props }) =>
    El(
      "button",
      {
        type: "button",
        className: `btn${primary ? " primary" : ""}`,
        ...props,
      },
      children,
    );
  const Link = ({ url, children }) =>
    linkUrl(url)
      ? El(
          "a",
          { href: linkUrl(url), target: "_blank", rel: "noopener noreferrer" },
          children || `${url} ↗`,
        )
      : "Brak danych";
  const Badge = ({ children, high }) =>
    El("span", { className: `badge${high ? " high" : ""}` }, children);
  const Notice = ({ children, error }) =>
    El("div", { className: `notice${error ? " error" : ""}` }, children);
  const Fact = ({ label, children }) =>
    El(
      "div",
      { className: "fact" },
      El("label", null, label),
      El("div", null, children),
    );
  const SectionTitle = ({ children }) =>
    El("h3", { className: "section-title" }, children);
  const Field = ({ label, id, children }) =>
    El(
      "div",
      { className: "field" },
      El("label", { htmlFor: id }, label),
      children,
    );
  const Option = ({ value, children }) => El("option", { value }, children);
  const bodyJson = (value) => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  });
  async function request(path, options) {
    const response = await fetch(path, options);
    let body = {};
    try {
      body = await response.json();
    } catch (_) {}
    if (!response.ok) {
      const detail = body.detail || body.message || `Błąd ${response.status}`;
      const error = new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
      error.status = response.status;
      throw error;
    }
    return body;
  }
  function Shell({ page, setPage, connection, children }) {
    const pages = [
      ["queue", "▦", "Kolejka"],
      ["sources", "◉", "Źródła"],
      ["calibration", "◫", "Jakość analizy"],
      ["upload", "▷", "Własne nagranie"],
    ];
    return El(
      "div",
      { className: "shell" },
      El(
        "aside",
        { className: "sidebar" },
        El(
          "div",
          { className: "brand" },
          El("div", { className: "brand-mark" }, "iW"),
          El(
            "div",
            { className: "brand-text" },
            El("b", null, "InvestWatch"),
            El("small", null, "STANOWISKO ANALITYKA"),
          ),
        ),
        El(
          "div",
          null,
          El("div", { className: "nav-label" }, "Przestrzeń pracy"),
          El(
            "nav",
            { className: "nav", "aria-label": "Nawigacja główna" },
            pages.map(([id, icon, label]) =>
              El(
                "button",
                {
                  key: id,
                  type: "button",
                  className: page === id ? "active" : "",
                  title: label,
                  onClick: () => setPage(id),
                },
                El("span", null, icon),
                El("em", { style: { fontStyle: "normal" } }, label),
              ),
            ),
          ),
        ),
        El(
          "div",
          { className: "sidebar-foot" },
          "UKNF / #InvestWatch",
          El("br"),
          "Wsparcie pracy analityka",
          El("br"),
          "Decyzja należy do człowieka.",
        ),
      ),
      El(
        "main",
        { className: "main", id: "main" },
        El(
          "div",
          { className: "topbar" },
          El(
            "div",
            { className: "topbar-title" },
            El("strong", null, "InvestWatch"),
            " / ",
            pages.find((p) => p[0] === page)?.[2],
          ),
          El(
            "div",
            { className: "connection" },
            El("span", { className: `dot${connection ? "" : " off"}` }),
            connection ? "Połączenie aktywne" : "Łączenie ponowne",
          ),
        ),
        El("div", { className: "workspace" }, children),
      ),
    );
  }
  function Heading({ eyebrow, title, description, children }) {
    return El(
      "div",
      { className: "page-head" },
      El(
        "div",
        null,
        El("div", { className: "eyebrow" }, eyebrow),
        El("h1", null, title),
        El("p", null, description),
      ),
      children && El("div", { className: "actions" }, children),
    );
  }
  function Metrics({ findings, creators, sources }) {
    const items = [
      ["Wszystkie sygnały", findings.length, "w kolejce analityka"],
      [
        "Do sprawdzenia",
        findings.filter((f) => f.status !== "closed").length,
        "nowe i w analizie",
      ],
      ["Twórcy", creators.length, "odkryte profile"],
      ["Źródła", sources.length, "objęte przeglądem"],
    ];
    return El(
      "div",
      { className: "overview" },
      items.map(([label, n, sub]) =>
        El(
          "div",
          { className: "metric", key: label },
          El("span", { className: "metric-label" }, label),
          El("strong", null, n),
          El("small", null, sub),
        ),
      ),
    );
  }
  function Evidence({ finding }) {
    const video = useRef(null);
    const [active, setActive] = useState(null);
    const evidence = list(finding.evidence);
    const comparison = finding.modalityComparison;
    return El(
      React.Fragment,
      null,
      comparison &&
        El(
          "div",
          { className: "comparison" },
          El("div", { className: "eyebrow" }, "Co zmienia odsłuch"),
          El(
            "div",
            { className: "compare-values" },
            El(
              "div",
              null,
              El("small", null, "Sam opis"),
              El("strong", null, text(comparison.descriptionOnly), " / 100"),
            ),
            El("div", { className: "compare-arrow" }, "→"),
            El(
              "div",
              null,
              El("small", null, "Opis i mowa"),
              El("strong", null, text(comparison.withAudio), " / 100"),
            ),
          ),
          El(
            "p",
            { className: "subtle" },
            "Ten sam materiał sprawdzono ponownie po dodaniu treści mowy. Wynik jest sygnałem do sprawdzenia, nie decyzją.",
          ),
        ),
      finding.semantic?.status === "ready" &&
        El(
          "div",
          { className: "semantic-note" },
          El("div", { className: "eyebrow" }, "Sugestia podobieństwa e5"),
          El(
            "p",
            null,
            text(finding.semantic.label, "Sugestia do sprawdzenia"),
            finding.semantic.fragment
              ? ` · „${text(finding.semantic.fragment)}”`
              : "",
          ),
          El(
            "p",
            { className: "subtle" },
            `Podobieństwo cosinusowe: ${text(
              finding.semantic.cosineSimilarity,
            )}. To podobieństwo do wzorca, nie prawdopodobieństwo ani wynik reguł.`,
            finding.semantic.ambiguity
              ? " Wynik niejednoznaczny — wymaga rozstrzygnięcia."
              : "",
            finding.semantic.margin != null
              ? ` Odstęp od kolejnego wzorca: ${text(finding.semantic.margin)}.`
              : "",
          ),
        ),
      finding.mediaUrl &&
        El(
          React.Fragment,
          null,
          El(
            /\.(mp3|wav|m4a|aac|flac|ogg)(?:[?#]|$)/i.test(finding.mediaUrl)
              ? "audio"
              : "video",
            {
              ref: video,
              className: "media",
              controls: true,
              preload: "metadata",
              src: linkUrl(finding.mediaUrl),
            },
          ),
          El(
            "p",
            { className: "subtle" },
            "Kliknij czas przy fragmencie, aby przejść do tego miejsca w nagraniu.",
          ),
        ),
      evidence.length
        ? evidence.map((e, i) =>
            El(
              "div",
              {
                className: `evidence${active === i ? " evidence-active" : ""}`,
                key: `${e.kind}-${i}`,
              },
              El(
                "div",
                { className: "eyebrow" },
                kindLabel(e.kind),
                " ",
                e.start != null &&
                  El(
                    "button",
                    {
                      type: "button",
                      className: "timecode",
                      onClick: () => {
                        if (video.current) {
                          video.current.currentTime = Number(e.start);
                          video.current.play().catch(() => {});
                          setActive(i);
                        }
                      },
                    },
                    `▶ ${clock(e.start)}`,
                  ),
              ),
              El("p", null, "„", text(e.text, "Brak tekstu"), "”"),
              e.url && El("p", null, El(Link, { url: e.url })),
              e.kind === "screenshot" &&
                linkUrl(e.url) &&
                El(
                  "a",
                  {
                    href: linkUrl(e.url),
                    target: "_blank",
                    rel: "noopener noreferrer",
                  },
                  El("img", {
                    src: linkUrl(e.url),
                    alt: "Zrzut badanego materiału",
                    className: "evidence-image",
                  }),
                ),
              e.domUrl &&
                El(
                  "p",
                  null,
                  El(Link, { url: e.domUrl }, "Otwórz pomiar DOM ↗"),
                ),
            ),
          )
        : El(
            Notice,
            null,
            "Brak dostępnego fragmentu dowodowego. Sprawdź materiał źródłowy.",
          ),
      finding.mediaUrl &&
        El(
          "p",
          { className: "subtle" },
          "Zakres: ",
          finding.coverage
            ? text(finding.coverage)
            : "dostępne segmenty mowy i opis",
          finding.asrScope
            ? ` · zakres transkrypcji: ${text(finding.asrScope)}`
            : "",
          ". Obecność segmentów nie potwierdza kompletnej analizy całej ścieżki dźwiękowej.",
        ),
      list(finding.checks).length > 0 &&
        El(
          React.Fragment,
          null,
          El("hr", { className: "rule" }),
          El(SectionTitle, null, "Ustalenia do weryfikacji"),
          finding.checks.map((c, i) =>
            El(
              "div",
              { className: "check", key: c.id || i },
              El(
                "div",
                null,
                El("strong", null, text(c.label || c.id)),
                El(
                  "div",
                  { className: "subtle" },
                  text(c.evidence, ""),
                  " ",
                  c.url && El(Link, { url: c.url }, "Źródło ↗"),
                  c.measurements && El("div", null, text(c.measurements)),
                ),
              ),
              El(Badge, null, status(c.state)),
            ),
          ),
        ),
    );
  }
  function Decision({ finding, save, busy }) {
    const [value, setValue] = useState(finding.status || "reviewing");
    const [note, setNote] = useState("");
    return El(
      React.Fragment,
      null,
      El(
        Notice,
        null,
        "Ocena systemu jest wskazówką. Decyzję podejmuje analityk po sprawdzeniu źródła.",
      ),
      El(
        Field,
        { label: "Status sprawy", id: "decision" },
        El(
          "select",
          { id: "decision", value, onChange: (e) => setValue(e.target.value) },
          ["new", "reviewing", "closed"].map((s) =>
            El(Option, { key: s, value: s }, status(s)),
          ),
        ),
      ),
      El(
        Field,
        { label: "Uzasadnienie decyzji", id: "note" },
        El("textarea", {
          id: "note",
          value: note,
          onChange: (e) => setNote(e.target.value),
          placeholder: "Zapisz, co sprawdzono i dlaczego…",
        }),
      ),
      El(
        Button,
        {
          primary: true,
          disabled: busy,
          onClick: async () => {
            if (await save(finding, value, note)) setNote("");
          },
        },
        "Zapisz decyzję",
      ),
      El("hr", { className: "rule" }),
      El(SectionTitle, null, "Historia decyzji"),
      list(finding.history).length
        ? finding.history.map((item, i) =>
            El(
              "p",
              { className: "history", key: i },
              El("strong", null, status(item.status || item.action)),
              " · ",
              date(item.at || item.createdAt),
              El("br"),
              text(item.note, ""),
            ),
          )
        : El("p", { className: "subtle" }, "Brak zapisanych decyzji."),
    );
  }
  function Contract({ finding, save }) {
    const [endDate, setDate] = useState("");
    const [label, setLabel] = useState("Umowa");
    const [result, setResult] = useState(null);
    return El(
      React.Fragment,
      null,
      El(
        Notice,
        null,
        "Przykład demonstracyjny. Dokument i aneks nie są przypisane do rzeczywistej firmy.",
      ),
      El(
        "p",
        { className: "subtle", style: { marginTop: 14 } },
        "Porównaj datę zakończenia umowy z datą publikacji. Dodanie aneksu zapisuje nowe porównanie.",
      ),
      El(
        Field,
        { id: "contract-label", label: "Dokument" },
        El(
          "select",
          {
            id: "contract-label",
            value: label,
            onChange: (e) => setLabel(e.target.value),
          },
          El(Option, { value: "Umowa" }, "Umowa"),
          El(Option, { value: "Aneks" }, "Aneks"),
        ),
      ),
      El(
        Field,
        { id: "contract-date", label: "Data końca współpracy" },
        El("input", {
          id: "contract-date",
          type: "date",
          value: endDate,
          onChange: (e) => setDate(e.target.value),
        }),
      ),
      El(
        Button,
        {
          primary: true,
          onClick: async () => {
            const r = await save(finding, endDate, label);
            if (r) setResult(r);
          },
        },
        "Porównaj i zapisz",
      ),
      result &&
        El(
          "div",
          { className: "evidence" },
          El("div", { className: "eyebrow" }, "Wynik porównania"),
          El("p", null, text(result.result)),
          El(
            "p",
            { className: "subtle" },
            `Publikacja: ${text(result.publishedAt)} · ${text(
              result.label,
            )} do ${text(result.endDate)}`,
          ),
        ),
    );
  }
  function Detail({ finding, creator, save, saveContract, busy }) {
    const [tab, setTab] = useState("evidence");
    if (!finding)
      return El(
        "div",
        { className: "detail-empty" },
        "Wybierz materiał z kolejki, aby zobaczyć jego źródło i dowody.",
      );
    const tabs = [
      ["evidence", "Dowody"],
      ["decision", "Decyzja i historia"],
      ...(finding.contractDemo ? [["contract", "Umowa / aneks"]] : []),
    ];
    return El(
      "div",
      { className: "detail" },
      El(
        "div",
        { className: "detail-top" },
        El(
          "div",
          null,
          El(
            "div",
            { className: "eyebrow" },
            text(finding.module),
            " · Karta materiału",
          ),
          El("h2", null, text(finding.title, "Materiał do analizy")),
        ),
        El(
          Badge,
          { high: Number(finding.score) >= 60 },
          finding.score != null ? `${finding.score} / 100` : "Brak oceny",
        ),
      ),
      El(
        "p",
        { className: "detail-lead" },
        text(finding.summary, "Otwórz źródło i sprawdź dostępne dowody."),
      ),
      El("hr", { className: "rule" }),
      El(
        "div",
        { className: "facts" },
        El(
          Fact,
          { label: "Autor / podmiot" },
          text(creator?.name || finding.creatorName || finding.brand),
        ),
        El(Fact, { label: "Platforma" }, text(finding.platform)),
        El(
          Fact,
          { label: "Źródło" },
          El(Link, { url: finding.url || creator?.url }),
        ),
        El(
          Fact,
          { label: "Data / pochodzenie" },
          date(finding.publishedAt || finding.observedAt || finding.createdAt),
          " · ",
          finding.provenance
            ? text(finding.provenance)
            : modeLabel(finding.mode),
        ),
      ),
      El(
        "div",
        { className: "tabs" },
        tabs.map(([id, label]) =>
          El(
            "button",
            {
              type: "button",
              key: id,
              className: tab === id ? "active" : "",
              onClick: () => setTab(id),
            },
            label,
          ),
        ),
      ),
      El(
        "div",
        { className: "tab-body" },
        tab === "evidence"
          ? El(Evidence, { finding })
          : tab === "decision"
            ? El(Decision, { finding, save, busy })
            : El(Contract, { finding, save: saveContract }),
      ),
    );
  }
  function Trend({ findings }) {
    const groups = {};
    findings.forEach((f) => {
      const day = String(f.publishedAt || f.observedAt || "").slice(0, 10);
      if (/^\d{4}-\d\d-\d\d$/.test(day) && Number.isFinite(Number(f.score))) {
        (groups[day] ||= []).push(Number(f.score));
      }
    });
    const days = Object.keys(groups).sort().slice(-8);
    return El(
      "section",
      { className: "panel trend" },
      El(
        "div",
        null,
        El("div", { className: "eyebrow" }, "Sygnały w czasie"),
        El(SectionTitle, null, "Średni wynik według daty"),
        El(
          "p",
          { className: "subtle" },
          "Średnia dla materiałów z datą, nie pomiar zmiany ryzyka populacji.",
        ),
      ),
      days.length
        ? El(
            "div",
            { className: "trend-bars" },
            days.map((day) => {
              const mean = Math.round(
                groups[day].reduce((a, b) => a + b, 0) / groups[day].length,
              );
              return El(
                "div",
                {
                  className: "trend-item",
                  key: day,
                  title: `${day}: ${mean}/100, ${groups[day].length} materiałów`,
                },
                El("span", {
                  className: "trend-bar",
                  style: { height: `${Math.max(mean, 3)}%` },
                }),
                El("small", null, day.slice(5)),
                El("b", null, mean),
              );
            }),
          )
        : El(
            "p",
            { className: "subtle" },
            "Brak datowanych wyników do porównania.",
          ),
    );
  }
  function Queue({
    data,
    selected,
    select,
    openExample,
    save,
    saveContract,
    busy,
    refresh,
    scan,
  }) {
    const findings = list(data?.findings),
      creators = list(data?.creators),
      sources = list(data?.sources);
    const [filters, setFilters] = useState({
      q: "",
      module: "",
      platform: "",
      status: "",
      risk: "",
      from: "",
      to: "",
    });
    const creator = (f) => creators.find((c) => c.id === f.creatorId);
    const filtered = findings.filter((f) => {
      const c = creator(f),
        hay = [f.title, f.summary, f.platform, c?.name, f.url]
          .join(" ")
          .toLowerCase();
      const day = String(f.publishedAt || f.observedAt || "").slice(0, 10);
      return (
        (!filters.q || hay.includes(filters.q.toLowerCase())) &&
        (!filters.module || f.module === filters.module) &&
        (!filters.platform || f.platform === filters.platform) &&
        (!filters.status || f.status === filters.status) &&
        (!filters.risk ||
          (filters.risk === "high"
            ? Number(f.score) >= 60
            : Number(f.score) < 60)) &&
        (!filters.from || (day && day >= filters.from)) &&
        (!filters.to || (day && day <= filters.to))
      );
    });
    const current =
      findings.find((f) => String(f.id) === String(selected)) ||
      (!selected ? filtered[0] : null);
    const update = (name) => (e) =>
      setFilters((old) => ({ ...old, [name]: e.target.value }));
    const unique = (name) => [
      ...new Set(findings.map((f) => f[name]).filter(Boolean)),
    ];
    const lastFailure = list(data?.scans).find((s) => s.status === "failed");
    const examples = findings
      .filter((f) => f.synthetic && f.mediaUrl && f.module === "M1")
      .sort((a, b) =>
        a.id === "demo-studio-aurora"
          ? -1
          : b.id === "demo-studio-aurora"
            ? 1
            : 0,
      )
      .slice(0, 2);
    return El(
      React.Fragment,
      null,
      El(
        Heading,
        {
          eyebrow: "Przegląd materiałów",
          title: "Od sygnału do decyzji",
          description: "Sprawdź źródło, dowód i zapisz wynik analizy.",
        },
        El(Button, { onClick: refresh }, "↻ Odśwież"),
        El(
          Button,
          { onClick: () => scan("live"), disabled: busy },
          "Skanuj na żywo",
        ),
        El(
          Button,
          { primary: true, onClick: () => scan("replay"), disabled: busy },
          busy ? "Uruchamianie…" : "▶ Uruchom skan",
        ),
      ),
      lastFailure &&
        El(
          "div",
          { style: { marginBottom: 18 } },
          El(
            Notice,
            { error: true },
            El("strong", null, "Ostatni nieudany przebieg: "),
            date(lastFailure.updatedAt || lastFailure.createdAt),
            " · ",
            text(
              lastFailure.error,
              "Nie udało się zakończyć analizy. Sprawdź źródła i ponów próbę.",
            ),
          ),
        ),
      examples.length > 0 &&
        El(
          "div",
          { className: "example-link" },
          El(
            "div",
            null,
            El("strong", null, "Wzmianka ukryta w nagraniu"),
            El(
              "p",
              { className: "subtle" },
              "Przykład syntetyczny: porównaj opis z treścią mowy.",
            ),
          ),
          El(
            "div",
            { className: "actions" },
            examples.map((example, index) =>
              El(
                Button,
                {
                  key: example.id,
                  onClick: () => {
                    setFilters({
                      q: "",
                      module: "",
                      platform: "",
                      status: "",
                      risk: "",
                      from: "",
                      to: "",
                    });
                    openExample(example.id);
                  },
                },
                index === 0
                  ? "Otwórz przykład z nagrania →"
                  : `Drugi przykład: ${text(example.title)} →`,
              ),
            ),
          ),
        ),
      El(Metrics, { findings, creators, sources }),
      El(
        "div",
        { className: "layout" },
        El(
          "section",
          { className: "panel" },
          El(
            "div",
            { className: "panel-head" },
            El("h2", null, "Kolejka sygnałów"),
            El("span", { className: "count" }, `${filtered.length} wyników`),
          ),
          El(
            "div",
            { className: "filters" },
            El("input", {
              type: "search",
              placeholder: "Szukaj autora, firmy lub materiału",
              "aria-label": "Szukaj",
              value: filters.q,
              onChange: update("q"),
            }),
            El(
              "select",
              {
                "aria-label": "Filtr modułu",
                value: filters.module,
                onChange: update("module"),
              },
              El(Option, { value: "" }, "Wszystkie moduły"),
              unique("module").map((v) => El(Option, { key: v, value: v }, v)),
            ),
            El(
              "select",
              {
                "aria-label": "Filtr platformy",
                value: filters.platform,
                onChange: update("platform"),
              },
              El(Option, { value: "" }, "Wszystkie platformy"),
              unique("platform").map((v) =>
                El(Option, { key: v, value: v }, v),
              ),
            ),
            El(
              "select",
              {
                "aria-label": "Filtr statusu",
                value: filters.status,
                onChange: update("status"),
              },
              El(Option, { value: "" }, "Wszystkie statusy"),
              ["new", "reviewing", "closed"].map((v) =>
                El(Option, { key: v, value: v }, status(v)),
              ),
            ),
            El(
              "select",
              {
                "aria-label": "Filtr priorytetu",
                value: filters.risk,
                onChange: update("risk"),
              },
              El(Option, { value: "" }, "Każdy priorytet"),
              El(Option, { value: "high" }, "Wynik ≥ 60"),
              El(Option, { value: "low" }, "Wynik < 60"),
            ),
            El(
              "label",
              { className: "date-filter" },
              "Od daty",
              El("input", {
                type: "date",
                value: filters.from,
                onChange: update("from"),
              }),
            ),
            El(
              "label",
              { className: "date-filter" },
              "Do daty",
              El("input", {
                type: "date",
                value: filters.to,
                onChange: update("to"),
              }),
            ),
          ),
          El(
            "div",
            { className: "finding-list" },
            filtered.length
              ? filtered.map((f) =>
                  El(
                    "button",
                    {
                      type: "button",
                      key: f.id,
                      className: `finding${
                        current?.id === f.id ? " selected" : ""
                      }`,
                      onClick: () => select(f.id),
                    },
                    El("span", { className: "module" }, text(f.module, "—")),
                    El(
                      "span",
                      null,
                      El(
                        "span",
                        { className: "finding-top" },
                        El(
                          "span",
                          { className: "finding-title" },
                          text(f.title, "Materiał do analizy"),
                        ),
                        El(
                          Badge,
                          { high: Number(f.score) >= 60 },
                          f.score ?? "—",
                        ),
                      ),
                      El(
                        "span",
                        { className: "finding-meta" },
                        text(creator(f)?.name || f.creatorName || f.platform),
                        " · ",
                        status(f.status || "new"),
                        El("br"),
                        text(f.summary, ""),
                      ),
                    ),
                  ),
                )
              : El(
                  "div",
                  { className: "empty" },
                  "Brak materiałów dla wybranych filtrów. Zmień filtry lub uruchom skan.",
                ),
          ),
        ),
        El(
          "section",
          { className: "panel", id: "detail" },
          El(Detail, {
            key: current?.id || "empty",
            finding: current,
            creator: current && creator(current),
            save,
            saveContract,
            busy,
          }),
        ),
      ),
      El(Trend, { findings: filtered }),
    );
  }
  function Sources({ data }) {
    const sources = list(data?.sources),
      creators = list(data?.creators),
      scans = list(data?.scans);
    return El(
      React.Fragment,
      null,
      El(Heading, {
        eyebrow: "Monitoring",
        title: "Źródła i twórcy",
        description: "Stan dostępności źródeł oraz pochodzenie materiałów.",
      }),
      El(
        "div",
        { className: "grid-cards" },
        sources.length
          ? sources.map((s, i) =>
              El(
                "article",
                { className: "panel source-card", key: s.id || s.name || i },
                El(
                  Badge,
                  {
                    high: ["error", "failed", "unavailable"].includes(s.status),
                  },
                  status(s.status),
                ),
                El("h3", { style: { marginTop: 12 } }, text(s.name || s.id)),
                El(
                  "p",
                  null,
                  `${s.count ?? 0} materiałów · ostatni sukces: ${date(
                    s.lastSuccessAt || s.lastSuccess || s.last_success,
                  )}`,
                ),
                s.error && El(Notice, { error: true }, text(s.error)),
              ),
            )
          : El(
              "div",
              { className: "empty" },
              "Brak informacji o źródłach. Uruchom skan lub spróbuj ponownie.",
            ),
      ),
      El(
        "h2",
        { className: "section-title", style: { margin: "30px 0 14px" } },
        "Odkryci twórcy ",
        El("span", { className: "count" }, creators.length),
      ),
      El(
        "div",
        { className: "grid-cards" },
        creators.length
          ? creators.map((c) =>
              El(
                "article",
                { className: "panel source-card", key: c.id },
                El("div", { className: "eyebrow" }, text(c.platform)),
                El("h3", null, text(c.name)),
                El("p", null, El(Link, { url: c.url })),
                El("p", null, "Odkryto przez: ", text(c.discoveredVia)),
                El("p", null, "Pierwsza obserwacja: ", date(c.firstSeen)),
              ),
            )
          : El("p", { className: "subtle" }, "Brak odkrytych twórców."),
      ),
      El(
        "h2",
        { className: "section-title", style: { margin: "30px 0 14px" } },
        "Ostatnie przebiegi",
      ),
      El(
        "div",
        { className: "panel source-card" },
        scans.length
          ? scans
              .slice(0, 8)
              .map((s) =>
                El(
                  "div",
                  { className: "check", key: s.id },
                  El(
                    "span",
                    null,
                    date(s.createdAt),
                    " · ",
                    modeLabel(s.mode),
                    s.error && ` · ${s.error}`,
                  ),
                  El(Badge, null, status(s.status)),
                ),
              )
          : El("p", { className: "subtle" }, "Brak zapisanych przebiegów."),
      ),
    );
  }
  function Calibration() {
    const [threshold, setThreshold] = useState(60),
      [cal, setCal] = useState(null),
      [retry, setRetry] = useState(0),
      [expanded, setExpanded] = useState(null);
    useEffect(() => {
      let active = true;
      const timer = setTimeout(
        () =>
          request(`/v1/calibration?threshold=${threshold}`)
            .then((x) => {
              if (active) setCal(x);
            })
            .catch((e) => {
              if (active) setCal({ error: e.message });
            }),
        150,
      );
      return () => {
        active = false;
        clearTimeout(timer);
      };
    }, [threshold, retry]);
    return El(
      React.Fragment,
      null,
      El(Heading, {
        eyebrow: "Jakość analizy",
        title: "Próg i wyniki",
        description: "Porównaj wyniki na tym samym zbiorze.",
      }),
      El(
        "section",
        { className: "panel calibration" },
        El("div", { className: "eyebrow" }, "Zamrożona próbka"),
        El(SectionTitle, null, `Próg kierowania do analizy: ${threshold}`),
        El(
          "p",
          { className: "subtle", style: { margin: "12px 0 20px" } },
          "Niższy próg może wykryć więcej przypadków, ale zwiększyć liczbę alarmów do sprawdzenia.",
        ),
        El("input", {
          type: "range",
          min: 0,
          max: 100,
          value: threshold,
          "aria-label": "Próg klasyfikacji",
          onChange: (e) => setThreshold(Number(e.target.value)),
        }),
        cal?.error
          ? El(
              Notice,
              { error: true },
              "Nie można pobrać wyników: ",
              cal.error,
              " ",
              El(
                Button,
                { onClick: () => setRetry(retry + 1) },
                "Spróbuj ponownie",
              ),
            )
          : cal
            ? El(
                React.Fragment,
                null,
                El(
                  "div",
                  { className: "numbers" },
                  [
                    ["tp", "Trafienia"],
                    ["fp", "Fałszywe alarmy"],
                    ["tn", "Poprawnie odrzucone"],
                    ["fn", "Przeoczenia"],
                  ].map(([key, label]) =>
                    El(
                      "div",
                      { className: "number", key },
                      El("small", null, label),
                      El("strong", null, text(cal[key], "—")),
                    ),
                  ),
                ),
                El(
                  "p",
                  { className: "subtle" },
                  `Liczba przykładów: ${text(cal.n)} · Zbiór: ${text(
                    cal.datasetId,
                  )} · Koszt operacyjny: ${text(cal.cost)}`,
                ),
                El(
                  "p",
                  { className: "subtle", style: { marginTop: 12 } },
                  text(
                    cal.description,
                    "Wynik zależy od składu próbki i wymaga oceny analityka.",
                  ),
                ),
                list(cal.errors).length > 0 &&
                  El(
                    React.Fragment,
                    null,
                    El("hr", { className: "rule" }),
                    El(SectionTitle, null, "Przypadki wymagające uwagi"),
                    cal.errors.map((x) =>
                      El(
                        "div",
                        { className: "check", key: x.id },
                        El(
                          "span",
                          null,
                          text(x.title || x.id),
                          " · ",
                          x.outcome === "fp" ? "fałszywy alarm" : "przeoczenie",
                          " · wynik ",
                          text(x.score),
                        ),
                        El(
                          Button,
                          {
                            onClick: () =>
                              setExpanded(expanded === x.id ? null : x.id),
                          },
                          expanded === x.id ? "Zamknij" : "Otwórz →",
                        ),
                        expanded === x.id &&
                          El(
                            "div",
                            { className: "cal-example" },
                            El("strong", null, "Materiał źródłowy"),
                            El("p", null, text(x.text)),
                            El(
                              "p",
                              null,
                              `Oczekiwano: ${
                                x.expected
                                  ? "sygnał do analizy"
                                  : "brak sygnału"
                              } · Wynik: ${text(x.score)} / 100 · ${
                                x.outcome === "fp"
                                  ? "fałszywy alarm"
                                  : "przeoczenie"
                              }`,
                            ),
                            x.url && El("p", null, El(Link, { url: x.url })),
                          ),
                      ),
                    ),
                  ),
              )
            : El("p", { className: "loading" }, "Pobieranie wyników…"),
      ),
    );
  }
  function Upload({ upload, busy, lastUpload, openUpload }) {
    const [title, setTitle] = useState(""),
      [description, setDescription] = useState(""),
      [file, setFile] = useState(null);
    return El(
      React.Fragment,
      null,
      El(Heading, {
        eyebrow: "Analiza nagrania",
        title: "Własny materiał",
        description: "Prześlij plik do lokalnej analizy i przejdź do dowodów.",
      }),
      El(
        "section",
        { className: "panel calibration" },
        El("div", { className: "eyebrow" }, "Materiał lokalny"),
        El(SectionTitle, null, "Prześlij nagranie do analizy"),
        El(
          "p",
          { className: "subtle", style: { marginTop: 10 } },
          "Wybierz plik audio lub wideo. Po zakończeniu analizy wynik pojawi się w kolejce wraz z dostępnymi fragmentami.",
        ),
        El(
          Field,
          { label: "Tytuł materiału", id: "upload-title" },
          El("input", {
            id: "upload-title",
            value: title,
            onChange: (e) => setTitle(e.target.value),
            placeholder: "Np. nagranie do sprawdzenia",
          }),
        ),
        El(
          Field,
          { label: "Opis (opcjonalnie)", id: "upload-description" },
          El("textarea", {
            id: "upload-description",
            value: description,
            onChange: (e) => setDescription(e.target.value),
            placeholder: "Kontekst materiału",
          }),
        ),
        El(
          Field,
          { label: "Plik audio lub wideo", id: "upload-file" },
          El("input", {
            id: "upload-file",
            type: "file",
            accept: "audio/*,video/*",
            onChange: (e) => setFile(e.target.files[0] || null),
          }),
        ),
        El(
          Button,
          {
            primary: true,
            disabled: busy,
            onClick: () => upload(file, title, description),
          },
          busy ? "Przesyłanie…" : "Prześlij do analizy",
        ),
        lastUpload &&
          El(
            "div",
            { style: { marginTop: 16 } },
            El(
              Button,
              { onClick: openUpload },
              "Przejdź do przesłanej analizy →",
            ),
          ),
      ),
    );
  }
  function App() {
    const [data, setData] = useState(null),
      [page, setPage] = useState("queue"),
      [selected, setSelected] = useState(null);
    const [connection, setConnection] = useState(false),
      [error, setError] = useState(""),
      [busy, setBusy] = useState(false),
      [toast, setToast] = useState(""),
      [lastUpload, setLastUpload] = useState(null);
    const toastTimer = useRef(null),
      refreshTimer = useRef(null),
      inFlight = useRef(false),
      again = useRef(false);
    const notify = useCallback((message) => {
      setToast(message);
      clearTimeout(toastTimer.current);
      toastTimer.current = setTimeout(() => setToast(""), 6000);
    }, []);
    const refresh = useCallback(async () => {
      if (inFlight.current) {
        again.current = true;
        return;
      }
      inFlight.current = true;
      try {
        setData(await request("/v1/state"));
        setError("");
      } catch (e) {
        setError(`Nie można pobrać danych: ${e.message}`);
      } finally {
        inFlight.current = false;
        if (again.current) {
          again.current = false;
          clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(refresh, 400);
        }
      }
    }, []);
    const scheduleRefresh = useCallback(() => {
      clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(refresh, 400);
    }, [refresh]);
    useEffect(() => {
      refresh();
      let ws,
        reconnect,
        closed = false,
        delay = 1000;
      function connect() {
        if (closed) return;
        ws = new WebSocket(
          `${location.protocol === "https:" ? "wss" : "ws"}://${
            location.host
          }/v1/events`,
        );
        ws.onopen = () => {
          setConnection(true);
          delay = 1000;
          scheduleRefresh();
        };
        ws.onmessage = scheduleRefresh;
        ws.onclose = () => {
          setConnection(false);
          if (!closed) {
            reconnect = setTimeout(connect, delay);
            delay = Math.min(delay * 2, 15000);
          }
        };
        ws.onerror = () => ws.close();
      }
      connect();
      return () => {
        closed = true;
        clearTimeout(reconnect);
        clearTimeout(refreshTimer.current);
        clearTimeout(toastTimer.current);
        ws?.close();
      };
    }, [refresh, scheduleRefresh]);
    const follow = () => {
      refresh();
      [1000, 3000, 7000, 15000].forEach((ms) =>
        setTimeout(scheduleRefresh, ms),
      );
    };
    async function scan(mode) {
      setBusy(true);
      try {
        await request(
          "/v1/scans",
          bodyJson({
            mode,
            requestId: globalThis.crypto?.randomUUID?.() || String(Date.now()),
          }),
        );
        notify("Skan uruchomiony. Wyniki pojawią się w kolejce.");
        follow();
      } catch (e) {
        notify(`Nie uruchomiono skanu: ${e.message}`);
      } finally {
        setBusy(false);
      }
    }
    async function save(finding, value, note) {
      if (!note.trim()) {
        notify("Wpisz uzasadnienie decyzji.");
        return false;
      }
      setBusy(true);
      try {
        await request(`/v1/cases/${encodeURIComponent(finding.id)}`, {
          ...bodyJson({
            status: value,
            expectedRevision: finding.revision,
            note,
          }),
          method: "PATCH",
        });
        notify("Decyzja została zapisana.");
        await refresh();
        return true;
      } catch (e) {
        if (e.status === 409) {
          await refresh();
          notify(
            "Sprawa została zmieniona. Pobrano aktualną wersję; sprawdź ją przed ponownym zapisem.",
          );
        } else notify(`Nie zapisano decyzji: ${e.message}`);
        return false;
      } finally {
        setBusy(false);
      }
    }
    async function saveContract(finding, endDate, label) {
      if (!endDate) {
        notify("Podaj datę końca współpracy.");
        return null;
      }
      try {
        const result = await request(
          `/v1/cases/${encodeURIComponent(finding.id)}/contract`,
          bodyJson({ endDate, label, expectedRevision: finding.revision }),
        );
        notify("Porównanie zostało zapisane.");
        refresh();
        return result;
      } catch (e) {
        if (e.status === 409) {
          await refresh();
          notify("Sprawa została zmieniona. Pobrano aktualną wersję.");
        } else notify(`Nie zapisano porównania: ${e.message}`);
        return null;
      }
    }
    async function upload(file, title, description) {
      if (!file) {
        notify("Wybierz plik audio lub wideo.");
        return;
      }
      setBusy(true);
      try {
        const params = new URLSearchParams({
          title: title || file.name,
          description,
          filename: file.name,
        });
        const result = await request(`/v1/media?${params}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        });
        setLastUpload(result.scanId);
        notify(
          "Materiał przesłany. Po zakończeniu wybierz „Przejdź do przesłanej analizy”.",
        );
        follow();
      } catch (e) {
        notify(`Nie przesłano materiału: ${e.message}`);
      } finally {
        setBusy(false);
      }
    }
    function openUpload() {
      const finding = list(data?.findings).find(
        (f) => f.id === `upload-${lastUpload}`,
      );
      if (finding) {
        setSelected(finding.id);
        setPage("queue");
        return;
      }
      const job = list(data?.scans).find(
        (s) => s.id === lastUpload || s.scanId === lastUpload,
      );
      notify(
        job?.status === "failed"
          ? `Analiza nie powiodła się: ${text(job.error)}`
          : "Analiza jeszcze trwa. Spróbuj za chwilę.",
      );
      scheduleRefresh();
    }
    function openFinding(item) {
      if (list(data?.findings).some((f) => f.id === item.id)) {
        setSelected(item.id);
        setPage("queue");
      } else
        notify(
          `Przykład z próbki: ${text(item.title)}. ${text(
            item.text,
            "Ten przykład nie ma osobnej sprawy w kolejce.",
          )}`,
        );
    }
    const common = {
      data,
      selected,
      select: setSelected,
      openExample: (id) => {
        setSelected(id);
        document
          .getElementById("detail")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      },
      save,
      saveContract,
      busy,
      refresh,
      scan,
    };
    return El(
      Shell,
      { page, setPage, connection },
      error &&
        El(
          "div",
          { style: { marginBottom: 18 } },
          El(
            Notice,
            { error: true },
            error,
            " ",
            El(Button, { onClick: refresh }, "Spróbuj ponownie"),
          ),
        ),
      !data && !error
        ? El("div", { className: "loading" }, "Pobieranie danych…")
        : page === "queue"
          ? El(Queue, common)
          : page === "sources"
            ? El(Sources, { data })
            : page === "calibration"
              ? El(Calibration, { openFinding })
              : El(Upload, { upload, busy, lastUpload, openUpload }),
      toast && El("div", { className: "toast", role: "status" }, toast),
    );
  }
  ReactDOM.createRoot(document.getElementById("app")).render(El(App));
})();
