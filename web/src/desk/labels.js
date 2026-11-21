// Polskie nazwy i formaty pulpitu. Bez żargonu: „przesłanka do sprawdzenia”, nigdy „naruszenie”.

export const MODULES = { M1: "Materiały twórców", M2: "Oferty WWW", M3: "Doradztwo WWW" };
/** Nazwa modułu dla kontrolera (plakietka w kolejce i filtr). */
export const MODULE_NAME = { M1: "Finfluencer", M2: "Reklama firmy", M3: "Doradztwo" };
export const moduleName = (m) => MODULE_NAME[m] || m || "";
export const STATUS = { new: "Nowa", reviewing: "W kontroli", closed: "Zamknięta" };
export const ROUTES = {
  refer: "Do sprawdzenia",
  complete: "Uzupełnij dane",
  no_signal: "Bez przesłanki",
  insufficient: "Za mało danych",
};
export const BANDS = { strong: "mocna", moderate: "średnia", weak: "słaba" };
export const bandOfValue = (v) => (v == null ? null : v >= 75 ? "strong" : v >= 60 ? "moderate" : "weak");
export const VARIANTS = {
  rules_1_2: "reguły 1.2 (poprzednie)",
  qual_d: "kwalifikacja D (opis, mowa i kadry)",
  qual_d_model: "kwalifikacja D z modelem lokalnym",
};
export const SCAN_MODE = { live: "skan na żywo", replay: "odtworzenie skanu", recompute: "przeliczenie", enrich: "uzupełnienie transkrypcji", upload: "plik operatora" };
export const SCAN_STATUS = { queued: "w kolejce", running: "w toku", done: "zakończony", partial: "częściowy", failed: "nieudany" };
export const RESOLUTIONS = [
  { value: "refer_to_control", label: "Przekaż do kontroli", hint: "Materiał wymaga dalszej kontroli; sprawa zostaje w toku." },
  { value: "complete_data", label: "Uzupełnij dane", hint: "Brakuje danych do oceny (np. transkrypcji); sprawa zostaje w toku." },
  { value: "no_signal", label: "Bez sygnału", hint: "Po sprawdzeniu nie ma przesłanki; sprawa zostaje zamknięta." },
  { value: "close", label: "Zamknij", hint: "Zamknij bez dalszych działań, z uzasadnieniem." },
];
export const RESOLUTION_LABEL = Object.fromEntries(RESOLUTIONS.map((r) => [r.value, r.label]));
export const DISCLOSURE_KIND = {
  in_description: "w opisie",
  in_speech: "w mowie",
  in_frame: "w kadrze",
  platform_flag: "flaga płatnej promocji YouTube",
};
export const ORIGINS = {
  live: "na żywo",
  replay: "odtworzenie skanu",
  synthetic: "syntetyczny (studio zespołu)",
  upload: "plik operatora",
  import: "import",
};
export const PLATFORM_LABEL = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram", facebook: "Facebook", web: "WWW", WWW: "WWW", Studio: "Studio" };
export const platformLabel = (p) => PLATFORM_LABEL[p] || p || "";
export const COMPLETE_REASON = {
  transcript_pending: "Mowa czeka na transkrypcję.",
  transcript_unavailable: "Mowy nie zbadano: brak transkrypcji (np. TikTok: tylko podpis).",
  identity_unresolved: "Nie ustalono, która firma jest stroną współpracy.",
  visual_unexamined: "Obrazu i wideo nie zbadano: podpis bez oznaczenia nie jest wnioskiem.",
  market_unknown: "Nie ustalono, czy oferta jest kierowana do klientów w Polsce.",
  axes_incomplete: "Brakuje którejś z czterech cech rekomendacji.",
};
/** Stan kryterium M2 i cechy M3: [kolor plakietki, etykieta]. */
export const CHECK_STATE = {
  "przesłanka": ["orange", "przesłanka"],
  "spełnione": ["green", "spełnione"],
  "nie dotyczy": ["gray", "nie dotyczy"],
  "brak danych": ["yellow", "brak danych"],
  "częściowo": ["yellow", "częściowo"],
  "poza katalogiem": ["gray", "poza katalogiem"],
};
/** Uprawnienia M3 (identity.state z API): [kolor, etykieta]. Nieznany kod: etykieta z API. */
export const IDENTITY_STATE = {
  authorized_advice: ["green", "uprawniony"],
  investment_firm_agent: ["green", "agent firmy inwestycyjnej"],
  authorized_other_scope: ["yellow", "uprawniony w innym zakresie"],
  not_found: ["orange", "brak wpisu w przejrzanych wykazach"],
  no_identity: ["gray", "brak danych podmiotu na stronie"],
  name_collision: ["orange", "kolizja nazw"],
  register_failure: ["red", "awaria rejestru"],
  registry_failure: ["red", "awaria rejestru"],
};
export const ENTITY_ROW = { name: "nazwa", krs: "KRS", nip: "NIP", regon: "REGON" };
export const DISCLOSURE_ROW = {
  explicit_ad: "oznaczona reklama",
  platform_flag: "flaga płatnej promocji",
  partner_mention: "wzmianka o współpracy",
  affiliate_link_mention: "link afiliacyjny",
};
export const DISCLOSURE_WHERE = { in_description: "w opisie", in_speech: "w mowie", in_frame: "w kadrze", platform_flag: "flaga platformy", description: "w opisie" };
export const SOURCE_STATE = {
  skipped: ["neutral", "pominięty"],
  access_blocked: ["warning", "dostęp zablokowany"],
  ok: ["success", "działa"],
  empty: ["neutral", "działa, bez nowych materiałów"],
  partial: ["warning", "częściowo"],
  candidate: ["warning", "kandydaci do potwierdzenia"],
  limit: ["warning", "wyczerpana kwota"],
  needs_key: ["warning", "brak klucza"],
  unavailable: ["error", "niedostępne"],
  error: ["error", "błąd"],
  stale: ["neutral", "nieaktualne"],
};
export const DISCLOSURE = {
  in_description: "w opisie",
  in_speech: "w mowie",
  in_frame: "w kadrze",
  platform_flag: "flaga płatnej promocji YouTube",
  not_found_in_scope: "nie znaleziono w zbadanym zakresie",
  not_checked: "niesprawdzone",
};
export const REL_STATUS = {
  declared: "jawna współpraca",
  documented: "udokumentowana współpraca",
  probable: "prawdopodobna relacja, do potwierdzenia",
  none: "brak relacji z firmą",
  unknown: "nieustalona",
};
export const MODALITY = {
  title: "tytuł",
  description: "opis",
  transcript: "mowa",
  frames: "kadry",
  platformFlags: "flaga płatnej promocji",
  page: "strona",
};
export const COVER_STATE = {
  full: "zbadano w całości",
  partial: "zbadano częściowo",
  fragment: "tylko fragment",
  selected_moments: "wybrane momenty",
  not_collected: "nie zbadano",
  pending: "oczekuje",
  unavailable: "niedostępne",
  empty: "pusty",
  observed: "sprawdzono",
  missing: "brak",
  minimal: "minimalny",
  none: "brak",
};
export const EVIDENCE_ROLE = { claim: "twierdzenie", disclosure: "oznaczenie", context: "kontekst" };
export const EVIDENCE_KIND = {
  description: "opis",
  title: "tytuł",
  audio: "mowa",
  transcript: "mowa",
  subtitle: "napisy",
  frame: "kadr",
  screenshot: "zrzut strony",
  registry: "rejestr",
  semantic: "podobieństwo semantyczne",
  page: "strona",
};
export const DISCOVERY_METHOD = {
  seed: "Profil monitorowany (seed)",
  apple_search: "Apple Podcasts",
  youtube_search: "Wyszukiwanie YouTube",
  data_api_search: "Wyszukiwanie YouTube",
  data_api_playlist: "Lista przesłanych filmów",
  atom: "Kanał Atom",
  oembed: "Odnośnik z opisu (oEmbed)",
  crosslink: "Odnośnik z opisu",
  crosslink_oembed: "Odnośnik z opisu (oEmbed)",
  peertube_search: "PeerTube",
  ranking_import: "Import rankingu",
  watch_sqlite: "Archiwum obserwacji",
  fixture: "Próbka testowa",
  upload: "Plik operatora",
};
export const HISTORY_KIND = {
  content: "Zmiana treści",
  evidence: "Nowy dowód",
  analysis: "Przeliczenie",
  provenance: "Zmiana pochodzenia",
  decision: "Decyzja analityka",
  inquiry: "Korespondencja",
  contract: "Porównanie z umową",
};

const tz = { timeZone: undefined };
export const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric", ...tz });
};
export const fmtDay = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString("pl-PL", { day: "numeric", month: "short", ...tz });
};
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
/** „21 XI” (dzień i miesiąc rzymski), jak w nazwie odtworzonego skanu. */
export const fmtDayRoman = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : `${d.getDate()} ${ROMAN[d.getMonth() + 1]}`;
};
export const fmtTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", ...tz });
};
export const fmtDateTime = (iso) => (iso ? `${fmtDate(iso)}, ${fmtTime(iso)}` : "—");
export const fmtNumber = (n) => (Number.isFinite(Number(n)) && n !== null && n !== "" ? Number(n).toLocaleString("pl-PL") : null);

export const clock = (seconds) => {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${r}` : `${m}:${r}`;
};

export const isYoutube = (url) => /^https?:\/\/(?:www\.|m\.)?(?:youtube\.com|youtu\.be)\//i.test(String(url || ""));
export const timeLink = (url, start) => {
  if (!url) return null;
  if (start == null || !isYoutube(url)) return url;
  const next = new URL(url);
  next.searchParams.set("t", `${Math.floor(start)}s`);
  return next.toString();
};

/** Bezpieczny adres do atrybutu href: tylko http(s) i ścieżki względne. */
export const safeUrl = (url) => {
  if (typeof url !== "string" || !url.trim()) return null;
  try {
    const parsed = new URL(url, "http://localhost/");
    return /^https?:$/.test(parsed.protocol) ? url : null;
  } catch {
    return null;
  }
};

export function describeDiscovery(entry) {
  if (!entry) return "";
  const parts = [DISCOVERY_METHOD[entry.method] || entry.method || "Droga nieustalona"];
  if (entry.query) parts.push(`zapytanie „${entry.query}”`);
  if (entry.position != null || entry.rank != null) parts.push(`pozycja ${entry.position ?? entry.rank}${entry.page > 1 ? `, strona ${entry.page}` : ""}`);
  const at = entry.at || entry.observedAt;
  if (at) parts.push(fmtDateTime(at));
  return parts.join(" · ");
}

const VIEW_LABEL = { desktop: "komputer", phone: "telefon", tablet: "tablet" };
/** „desktop 1440×900” z API → „komputer 1440×900”. */
export const viewLabel = (viewport) => String(viewport || "").replace(/^(desktop|phone|tablet)/, (m) => VIEW_LABEL[m]);
