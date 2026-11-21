// Measure every rendered text block of a marketing page in the current Chromium viewport.
// Product-agnostic: the 19 UKNF checks run later in Python over these blocks.
({maxBlocks = 2500, maxChars = 700}) => {
  const strip = text => text.replace(/\s+/gu, " ").trim();
  const round = x => Math.round(x * 10) / 10;
  const BLOCKY = /^(block|list-item|table-cell|table-caption|flex|grid|flow-root|table|inline-block|inline-flex)$/;
  const LEAF = "p,li,h1,h2,h3,h4,h5,h6,td,th,dt,dd,figcaption,summary,button,label,blockquote,caption,legend";
  const HINTS = /legal|disclaimer|footnote|przypis|stopk|footer|risk|ryzyk|warning|ostrzez|nota|cookie|consent|gdpr|banner|modal|accordion|collapse|tooltip|popover|hero|promo|cta|disclosure|regulator|small|fine/gi;

  function container(node) {
    for (let el = node.parentElement; el && el !== document.body; el = el.parentElement) {
      if (el.matches(LEAF)) return el;
      const display = getComputedStyle(el).display;
      if (BLOCKY.test(display) && display !== "inline-block" && display !== "inline-flex") return el;
    }
    return document.body;
  }

  function hiddenReason(el) {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === "none") return "display:none";
      if (/^(hidden|collapse)$/.test(s.visibility)) return "visibility:hidden";
      if (Number(s.opacity) === 0) return "opacity:0";
      if (s.contentVisibility === "hidden") return "content-visibility";
      if (n.matches("details:not([open])") && !el.closest("summary")) return "details:closed";
      if (n.getAttribute && n.getAttribute("aria-hidden") === "true") return "aria-hidden";
      if (n.hidden) return "hidden";
      const r = n.getBoundingClientRect();
      if (n !== el && r.height < 2 && /^(hidden|clip)$/.test(s.overflowY)) return "collapsed";
    }
    return null;
  }

  function overlay(el) {
    if (el.closest("[role=dialog],[role=alertdialog],dialog,#CybotCookiebotDialog,#onetrust-banner-sdk,#onetrust-consent-sdk")) return true;
    // A cookie/consent wrapper counts only when it floats over the page (fixed or sticky), never a page-wide container.
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const words = (typeof n.className === "string" ? n.className : "") + " " + (n.id || "");
      if (/cookie|consent|gdpr/i.test(words) && /^(fixed|sticky)$/.test(getComputedStyle(n).position) && !n.querySelector("main,h1")) return true;
    }
    return false;
  }

  function role(el) {
    if (overlay(el)) return "dialog";
    if (el.closest("nav,[role=navigation],[role=menu],[role=menubar]")) return "nav";
    if (el.closest("footer,[role=contentinfo]")) return "footer";
    if (el.closest("header,[role=banner]")) return "header";
    const note = el.closest("small,sup,[role=doc-footnote],[role=note],.footnote,[class*=disclaimer i],[class*=legal i],[class*=footnote i]");
    // A page-wide wrapper whose class happens to contain "legal" is not a footnote.
    if (note && note.getBoundingClientRect().height < 0.3 * document.documentElement.scrollHeight && !note.querySelector("h1,h2,main")) return "footnote";
    return "body";
  }

  function hints(el) {
    const found = new Set();
    for (let n = el, depth = 0; n && n !== document.body && depth < 6; n = n.parentElement, depth++) {
      const words = ((typeof n.className === "string" ? n.className : "") + " " + (n.id || "")).toLowerCase();
      for (const m of words.matchAll(HINTS)) found.add(m[0]);
    }
    return [...found].slice(0, 8);
  }

  const sections = new Map();
  function section(el) {
    const s = el.closest("section,article,aside,footer,header,nav,form,dialog,[role=dialog],[role=region],li,table");
    if (!s) return 0;
    if (!sections.has(s)) sections.set(s, sections.size + 1);
    return sections.get(s);
  }

  function fixed(el) {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const p = getComputedStyle(n).position;
      if (p === "fixed" || p === "sticky") return p;
    }
    return null;
  }

  function rgb(value) {
    const m = /^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/.exec(value);
    return m ? [Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4] ?? 1)] : null;
  }
  function blend(front, back) {
    const a = front[3] + back[3] * (1 - front[3]);
    if (!a) return [0, 0, 0, 0];
    return [...front.slice(0, 3).map((v, i) => (v * front[3] + back[i] * back[3] * (1 - front[3])) / a), a];
  }
  function lum(c) {
    const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function contrast(el) {
    let bg = [0, 0, 0, 0];
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.filter !== "none" || s.mixBlendMode !== "normal") return {reason: "złożone nakładanie kolorów"};
      if (bg[3] < 1) {
        const c = rgb(s.backgroundColor);
        if (!c || s.backgroundImage !== "none") return {reason: "tło obrazem lub gradientem"};
        bg = blend(bg, c);
      }
    }
    bg = blend(bg, [255, 255, 255, 1]);
    const fg = rgb(getComputedStyle(el).color);
    if (!fg || !fg[3]) return {reason: "nieodczytany kolor tekstu"};
    const v = [lum(blend(fg, bg)), lum(bg)].sort((a, b) => b - a);
    return {ratio: Math.round((v[0] + 0.05) / (v[1] + 0.05) * 100) / 100};
  }

  function truncated(el) {
    for (let n = el, depth = 0; n && n !== document.body && depth < 3; n = n.parentElement, depth++) {
      const s = getComputedStyle(n);
      if (s.textOverflow === "ellipsis" && n.scrollWidth > n.clientWidth + 1) return "ellipsis";
      if (s.webkitLineClamp && s.webkitLineClamp !== "none" && n.scrollHeight > n.clientHeight + 2) return "line-clamp";
      if (/^(hidden|clip)$/.test(s.overflowY) && n.clientHeight > 0 && n.scrollHeight > n.clientHeight + 4 &&
          n.scrollHeight - n.clientHeight < 2000 && strip(n.innerText || "").length < 1500) return "overflow";
    }
    return null;
  }

  // Group visible-or-hidden text nodes by their nearest block container.
  const groups = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.data.trim()) continue;
    const parent = node.parentElement;
    if (!parent || parent.closest("script,style,noscript,template,svg,iframe")) continue;
    const c = container(node);
    if (!groups.has(c)) groups.set(c, []);
    groups.get(c).push(node);
  }

  const vh = innerHeight, vw = innerWidth;
  const blocks = [];
  let skippedHidden = 0;
  for (const [el, nodes] of groups) {
    const text = strip(nodes.map(n => n.data).join(" "));
    if (text.length < 2) continue;
    const hidden = hiddenReason(el);
    const blockRole = role(el);
    if (hidden && (blockRole === "nav" || blockRole === "dialog")) { skippedHidden++; continue; }
    const sizes = {}, weights = {};
    const rects = [];
    let visibleArea = 0, area = 0;
    for (const n of nodes) {
      const owner = n.parentElement;
      const st = getComputedStyle(owner);
      const chars = strip(n.data).replace(/\s/gu, "").length;
      sizes[st.fontSize] = (sizes[st.fontSize] ?? 0) + chars;
      weights[st.fontWeight] = (weights[st.fontWeight] ?? 0) + chars;
      if (hidden) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        if (!r.width || !r.height) continue;
        rects.push(r);
        area += r.width * r.height;
        const top = Math.max(0, r.top), bottom = Math.min(vh, r.bottom);
        const left = Math.max(0, r.left), right = Math.min(vw, r.right);
        if (bottom > top && right > left) visibleArea += (bottom - top) * (right - left);
      }
    }
    const pick = obj => Object.entries(obj).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
    const px = pick(sizes);
    let bbox = null, docBbox = null, occluded = null;
    if (rects.length) {
      const l = Math.min(...rects.map(r => r.left)), t = Math.min(...rects.map(r => r.top));
      const r_ = Math.max(...rects.map(r => r.right)), b = Math.max(...rects.map(r => r.bottom));
      bbox = [round(l), round(t), round(r_ - l), round(b - t)];
      docBbox = [round(l + scrollX), round(t + scrollY), bbox[2], bbox[3]];
      if (visibleArea > 0) {
        const cx = Math.min(vw - 1, Math.max(0, l + (r_ - l) / 2)), cy = Math.min(vh - 1, Math.max(0, t + Math.min(b - t, 30) / 2));
        const hit = document.elementFromPoint(cx, cy);
        occluded = !(hit && (el.contains(hit) || hit.contains(el)));
      }
    }
    const heading = el.matches("h1,h2,h3,h4,h5,h6") ? Number(el.localName[1]) :
      el.closest("[role=heading]") ? Number(el.closest("[role=heading]").getAttribute("aria-level") || 2) : null;
    const link = el.closest("a[href]");
    const c = hidden || !rects.length ? {reason: hidden ? "element ukryty" : "brak prostokątów"} : contrast(nodes[0].parentElement);
    blocks.push({
      t: text.slice(0, maxChars), n: text.length, tag: el.localName, h: heading,
      px: px ? parseFloat(px) : null, fw: pick(weights) ? Number(pick(weights)) : null,
      sizes: Object.fromEntries(Object.entries(sizes).map(([k, v]) => [parseFloat(k), v])),
      bbox: docBbox, first: area ? Math.round(visibleArea / area * 100) / 100 : 0,
      occ: occluded, hid: hidden, role: blockRole, sec: section(el), fix: fixed(el),
      cr: c.ratio ?? null, crw: c.reason ?? null, trunc: hidden ? null : truncated(el),
      lang: el.closest("[lang]")?.lang ?? null, href: link ? link.href.slice(0, 300) : null, hint: hints(el)
    });
    if (blocks.length >= maxBlocks) break;
  }
  const riskLinks = [...document.querySelectorAll("a[href]")]
    .filter(a => /ryzyk|ostrzeż|risk|warning|nota prawna|zastrzeżen/iu.test(a.innerText || a.getAttribute("aria-label") || ""))
    .slice(0, 20).map(a => ({t: strip(a.innerText || "").slice(0, 200), href: a.href.slice(0, 300)}));
  const main = document.querySelector("main,[role=main]") ?? document.body;
  return {
    width: vw, height: vh, scrollX: round(scrollX), scrollY: round(scrollY),
    docHeight: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth,
    title: (document.title || "").trim().slice(0, 300), lang: document.documentElement.lang || null,
    blocks, truncatedBlocks: blocks.length >= maxBlocks, skippedHiddenNavOrDialog: skippedHidden, riskLinks,
    text: main.innerText.trim().slice(0, 30000)
  };
}
