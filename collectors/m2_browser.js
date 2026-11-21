// Measure the quoted text and its DOM scope in the current Chromium viewport.
({product, action = null, legalName = ""}) => {
  const claims = /\b(?:prowizj\p{L}*\s*0\s*%|bez\s+prowizji|bezpłatn\p{L}*|brak opłat|0\s*zł|darmow\p{L}*)/iu;
  const profitClaim = /(?:źródł\p{L}*\s+dochodu.{0,35}dywidend\p{L}*|(?:możliw\p{L}*|potencjaln\p{L}*)\s+zysk\p{L}*|(?:zarabiaj|zarobisz)\s+odsetki|(?:otrzymuj|otrzymasz|zyskaj)\s+dywidend\p{L}*)/iu;
  const warnings = /\b(?:ryzykown\p{L}*|ryzyko\s+(?:inwestycyjn\p{L}*|(?:szybkiej )?utrat\p{L}*|strat\p{L}*)|ryzyki?e?m?\s+(?:szybkiej )?utrat\p{L}*|odnotow\p{L}*\s+strat\p{L}*|utrac\p{L}*\s+(?:część|całość|kapitał)|utrata kapitału)/iu;
  const adLabel = /\b(?:materiał (?:reklamowy|promocyjny)|komunikat marketingowy|to jest reklama)\b/iu;
  const products = {
    etf: /\betf(?:-?\p{L}+)?\b/iu,
    stocks: /\b(?:akcj\p{L}*|akcjonariusz\p{L}*)\b/iu,
    cfd: /\bcfd\b/iu,
    account: /\brachun(?:ek|ku|kiem|ki|ków|kach|kowi)\s+inwestycyjn\p{L}*\b/iu,
    retirement: /\b(?:ike|ikze|rachun(?:ek|ku|kiem|ki|ków)\s+emerytaln\p{L}*)\b/iu
  };
  const strip = text => text.replace(/\s+/gu, " ").trim();
  const round = x => Math.round(x * 100) / 100;
  const layout = box => [box.left, box.top, box.width, box.height].map(round);
  const tags = "h1,h2,h3,h4,h5,p,li,small,span,div,dt,dd,[role=heading]";
  const areaOf = rect => Math.max(0, rect[2] - rect[0]) * Math.max(0, rect[3] - rect[1]);

  function path(element) {
    const names = [];
    while (element && element !== document.body) {
      let index = 1;
      for (let prev = element.previousElementSibling; prev; prev = prev.previousElementSibling) {
        if (prev.localName === element.localName) index++;
      }
      names.unshift(element.localName + ":nth-of-type(" + index + ")");
      element = element.parentElement;
    }
    return "body > " + names.join(" > ");
  }

  function creative(element) {
    return element.closest("[data-ad-creative],.foundations-card-text,section,article,aside,footer,header");
  }

  function role(element) {
    if (element.closest("footer,[role=contentinfo]")) return "footer";
    if (element.closest("small,[role=doc-footnote],[role=note],.footnote")) return "footnote";
    if (element.closest("header,[role=banner]")) return "header";
    return "body";
  }

  function scopeOf(block, quote) {
    const local = creative(block);
    const heading = local?.querySelector("h1,h2,h3")?.textContent ?? "";
    const topics = text => Object.entries(products).filter(([, rx]) => rx.test(text)).map(([key]) => key);
    const direct = topics(quote);
    const paragraph = topics(block.textContent.replace(/tak jak w przypadku [^.]+/giu, ''));
    const inherited = topics(heading);
    // A CFD warning remains CFD even when the page or a footer also names ETF.
    if (direct.length) return direct;
    if (paragraph.length) return paragraph;
    if (local && role(block) === "body" && inherited.length === 1) return inherited;
    return [];
  }

  function rawText(element) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let text = "";
    const parts = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.parentElement.closest("script,style,template,[hidden]")) {
        parts.push({node, start: text.length});
        text += node.data;
      }
    }
    return {text, parts};
  }

  function matchRange(element, quotation) {
    const {text, parts} = rawText(element);
    if (!parts.length) return [];
    const from = quotation?.start ?? 0;
    const end = quotation?.end ?? text.length;
    if (from >= end) return [];
    return parts.flatMap(({node, start}) => {
      const lower = Math.max(0, from - start);
      const upper = Math.min(node.length, end - start);
      if (lower >= upper || !strip(node.data.slice(lower, upper))) return [];
      const range = new Range();
      range.setStart(node, lower);
      range.setEnd(node, upper);
      return [{node, count: strip(node.data.slice(lower, upper)).replace(/\s/gu, "").length, range}];
    });
  }

  function textBox(rects) {
    if (!rects.length) return null;
    const left = Math.min(...rects.map(rect => rect.left));
    const top = Math.min(...rects.map(rect => rect.top));
    const right = Math.max(...rects.map(rect => rect.right));
    const bottom = Math.max(...rects.map(rect => rect.bottom));
    return [left, top, right - left, bottom - top].map(round);
  }

  function styleVisibility(element) {
    for (let node = element; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === "none" || /^(hidden|collapse)$/.test(style.visibility) ||
          Number(style.opacity) === 0 || style.contentVisibility === "hidden") return false;
    }
    const details = element.closest("details:not([open])");
    return !details || Boolean(element.closest("summary")?.parentElement === details);
  }

  function visibleRect(element, box) {
    const limit = [Math.max(0, box.left), Math.max(0, box.top), Math.min(innerWidth, box.right), Math.min(innerHeight, box.bottom)];
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      const clip = node.getBoundingClientRect();
      if (/^(auto|hidden|scroll|clip)$/.test(style.overflowX) && clip.width) {
        limit[0] = Math.max(limit[0], clip.left + node.clientLeft);
        limit[2] = Math.min(limit[2], clip.left + node.clientLeft + node.clientWidth);
      }
      if (/^(auto|hidden|scroll|clip)$/.test(style.overflowY) && clip.height) {
        limit[1] = Math.max(limit[1], clip.top + node.clientTop);
        limit[3] = Math.min(limit[3], clip.top + node.clientTop + node.clientHeight);
      }
    }
    return limit;
  }

  function rgb(value) {
    const match = /^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/.exec(value);
    return match ? [Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4] ?? 1)] : null;
  }

  function blend(front, back) {
    const opacity = front[3] + back[3] * (1 - front[3]);
    if (!opacity) return [0, 0, 0, 0];
    return [...front.slice(0, 3).map((value, i) => (value * front[3] + back[i] * back[3] * (1 - front[3])) / opacity), opacity];
  }

  function luminance(color) {
    const [r, g, b] = color.slice(0, 3).map(channel => {
      const value = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrast(element) {
    let background = [0, 0, 0, 0];
    for (let node = element; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.opacity !== "1" || style.filter !== "none" || style.backdropFilter !== "none" || style.mixBlendMode !== "normal") {
        return {reason: "złożone nakładanie kolorów"};
      }
      if (background[3] < 1) {
        const color = rgb(style.backgroundColor);
        if (!color || style.backgroundImage !== "none") return {reason: "złożone tło CSS"};
        for (const side of ["::before", "::after"]) {
          const pseudo = getComputedStyle(node, side);
          if (pseudo.content !== "none" && pseudo.content !== "normal" &&
              (pseudo.backgroundImage !== "none" || (rgb(pseudo.backgroundColor)?.[3] ?? 1) > 0)) {
            return {reason: "warstwa pseudo-elementu"};
          }
        }
        background = blend(background, color);
      }
    }
    background = blend(background, [255, 255, 255, 1]);
    const foreground = rgb(getComputedStyle(element).color);
    if (!foreground || !foreground[3]) return {reason: "nieodczytany kolor tekstu"};
    const values = [luminance(blend(foreground, background)), luminance(background)].sort((a, b) => b - a);
    return {ratio: round((values[0]+0.05)/(values[1]+0.05)), foreground, background: background.map(round)};
  }

  function measure(element, quotation) {
    const parts = matchRange(element, quotation);
    const rects = [];
    const sizes = {};
    const contrasts = [];
    let total = 0;
    let clipped = 0;
    let visible = 0;
    for (const {node, range, count} of parts) {
      const owner = node.parentElement;
      if (!styleVisibility(owner)) continue;
      const boxes = [...range.getClientRects()].filter(box => box.width && box.height);
      const px = getComputedStyle(owner).fontSize;
      let partArea = 0;
      let partVisible = 0;
      for (const box of boxes) {
        const boxArea = box.width * box.height;
        const limit = visibleRect(owner, box);
        const area = areaOf(limit);
        rects.push(box);
        total += boxArea;
        partArea += boxArea;
        if (!area) continue;
        clipped += area;
        let visibleSamples = 0;
        for (const x of [0.15, 0.5, 0.85]) {
          const hit = document.elementFromPoint(limit[0] + x * (limit[2] - limit[0]), (limit[1] + limit[3]) / 2);
          if (hit && (owner.contains(hit) || hit.contains(owner))) visibleSamples++;
        }
        partVisible += area * visibleSamples / 3;
      }
      if (partArea) {
        sizes[px] = (sizes[px] ?? 0) + count * partVisible / partArea;
        if (partVisible) contrasts.push(contrast(owner));
      }
      visible += partVisible;
    }
    const bounds = element.getBoundingClientRect();
    const bbox = textBox(rects) ?? layout(bounds);
    const px = Object.keys(sizes);
    const unknown = contrasts.find(entry => typeof entry.ratio !== "number");
    const minimum = unknown ?? contrasts.sort((a, b) => a.ratio - b.ratio)[0];
    return {
      text: quotation?.text ?? strip(element.textContent).slice(0, 500),
      selector: path(element), productScope: scopeOf(element, quotation?.text ?? ""),
      bbox, documentBbox: [round(bbox[0] + scrollX), round(bbox[1] + scrollY), ...bbox.slice(2)],
      px: px.length === 1 ? px[0] : null,
      clipFraction: total ? round(clipped / total) : 0,
      visibleFraction: total ? round(visible / total) : 0,
      occluded: clipped > 0 && visible / clipped < 0.98,
      contrast: minimum?.ratio ?? null,
      contrastReason: minimum?.reason ?? (contrasts.length ? null : "tekst poza widoczną częścią ekranu"),
      foreground: minimum?.foreground ?? null, background: minimum?.background ?? null,
      role: role(element), sizes, language: element.closest("[lang]")?.lang ?? null
    };
  }

  function sentence(element, pattern) {
    const {text} = rawText(element);
    const hit = pattern.exec(text);
    if (!hit) return null;
    const delimiters = [...text.slice(0, hit.index).matchAll(/[.!?]\s+/gu)];
    const last = delimiters.at(-1);
    const start = last ? last.index + last[0].length : 0;
    const endPunctuation = /[.!?](?:\s|$)/u.exec(text.slice(hit.index + hit[0].length));
    const end = endPunctuation ? hit.index + hit[0].length + endPunctuation.index + 1 : text.length;
    return {start, end, text: strip(text.slice(start, end)).slice(0, 500)};
  }

  const blocks = [...document.querySelectorAll(tags)].filter(element => {
    if (element.closest("script,style,template,svg,[aria-hidden=true]")) return false;
    if (["DIV","SPAN"].includes(element.tagName) && element.querySelector(tags)) return false;
    const length = strip(element.textContent).length;
    return length >= 6 && length <= 900;
  });
  const productRx = products[product];
  const benefitCandidates = blocks.filter(element => claims.test(element.textContent) &&
    !element.closest("nav,footer,[role=navigation]") && !warnings.test(element.textContent));
  const benefit = benefitCandidates.find(node => node.matches("h1") && productRx.test(node.textContent)) ||
    benefitCandidates.find(node => productRx.test(node.textContent)) || null;
  const profit = blocks.find(node => {
    if (!profitClaim.test(node.textContent) || !productRx.test(node.textContent) ||
        node.closest("nav,footer,[role=navigation]") || warnings.test(node.textContent)) return false;
    const quote = sentence(node, profitClaim);
    const scope = quote ? scopeOf(node, quote.text) : [];
    return scope.length === 1 && scope[0] === product;
  }) ?? null;
  const strategy = [];
  for (const node of blocks) {
    if (!warnings.test(node.textContent) || node.closest("nav,[role=navigation]")) continue;
    if (strategy.some(item => item.node.contains(node) && strip(item.node.textContent).includes(strip(node.textContent)))) continue;
    const quote = sentence(node, warnings);
    if (!quote) continue;
    const scope = scopeOf(node, quote.text);
    let relation = "unknown_scope";
    if (scope.length && !scope.includes(product)) relation = "different_product";
    if (scope.length === 1 && scope[0] === product) {
      relation = benefit && (node === benefit || (creative(node) && creative(node) === creative(benefit)))
        ? "same_creative" : "same_product";
    }
    strategy.push({node, quote, relation});
  }
  const warning = strategy.find(item => item.relation === "same_creative") ??
    strategy.find(item => item.relation === "same_product") ?? null;
  const other = strategy.find(item => item.relation === "different_product") ?? null;
  const legalSearch = legalName.toLocaleLowerCase("pl");
  const legal = legalSearch && blocks.find(element => strip(element.textContent).toLocaleLowerCase("pl").includes(legalSearch));
  if (["claim", "warning", "identity", "profit"].includes(action)) {
    const targets = {claim: benefit, warning: warning?.node, identity: legal, profit};
    const element = targets[action];
    if (element) element.scrollIntoView({block: "center", inline: "nearest", behavior: "instant"});
    return Boolean(element);
  }

  function dominant(element) {
    if (!element) return null;
    const region = creative(element);
    if (!region || ["BODY","MAIN","HEADER","FOOTER"].includes(region.tagName)) return null;
    const counts = {};
    const parts = matchRange(region, null);
    if (parts.length > 350) return null;
    for (const {node} of parts) {
      const owner = node.parentElement;
      if (owner.closest("nav,footer,header,[role=navigation],script,style,template")) continue;
      // A visible text node contributes once even when nested inside formatting.
      const text = node.data;
      const totalChars = strip(text).replace(/\s/gu, "").length;
      if (!totalChars || !styleVisibility(owner)) continue;
      const range = new Range();
      range.selectNodeContents(node);
      let visibleChars = 0;
      for (const box of range.getClientRects()) {
        if (!box.width || !box.height) continue;
        const view = visibleRect(owner, box);
        const area = areaOf(view);
        if (!area) continue;
        const hit = document.elementFromPoint((view[0] + view[2])/2, (view[1] + view[3])/2);
        if (hit && (owner.contains(hit) || hit.contains(owner))) visibleChars += area / box.height;
      }
      const width = [...range.getClientRects()].reduce((sum, box) => sum + box.width, 0);
      const px = getComputedStyle(owner).fontSize;
      if (width) counts[px] = (counts[px] ?? 0) + totalChars * visibleChars / width;
    }
    const sorted = Object.entries(counts).filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1]);
    return {selector: path(region), px: sorted.length && (!sorted[1] || sorted[0][1] - sorted[1][1] >= 1) ? sorted[0][0] : null,
      visibleCharacterCounts: Object.fromEntries(sorted.map(([px, value]) => [px, round(value)]))};
  }

  const benefitData = benefit ? measure(benefit, sentence(benefit, claims)) : null;
  const warningData = warning ? {
    ...measure(warning.node, warning.quote), productScope: scopeOf(warning.node, warning.quote.text),
    scopeContext: strip(warning.node.textContent).slice(0, 500)
  } : null;
  let legalData = null;
  if (legal) {
    const sourceText = rawText(legal).text;
    const start = sourceText.toLocaleLowerCase("pl").indexOf(legalSearch);
    const end = start + legalSearch.length;
    legalData = start >= 0 ? measure(legal, {start, end, text: sourceText.slice(start, end)}) : measure(legal, null);
  }
  const label = blocks.find(element => adLabel.test(strip(element.textContent)) && !element.closest("footer,nav"));
  const main = document.querySelector("main,[role=main],#content") ?? document.body;
  const scopeText = main.innerText.trim().slice(0, 24000);
  return {
    width: innerWidth, height: innerHeight, scrollX: round(scrollX), scrollY: round(scrollY),
    consentOverlay: [...document.querySelectorAll("[role=dialog],dialog,#CybotCookiebotDialog")].some(element => {
      const box = element.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && styleVisibility(element) &&
        /cookie|ciastecz|zgod[yaę]/iu.test(element.textContent);
    }),
    title: (document.title || document.querySelector("h1")?.innerText || "").trim().slice(0, 300),
    textScope: scopeText, language: document.documentElement.lang,
    benefit: benefitData, warning: warningData, relation: warning?.relation ?? null,
    profit: profit ? measure(profit, sentence(profit, profitClaim)) : null,
    profitRelation: profit && warning
      ? creative(profit) && creative(profit) === creative(warning.node) ? "same_creative" : "same_product"
      : null,
    rejectedWarning: other ? measure(other.node, other.quote) : null,
    warningCandidates: strategy.slice(0, 30).map(item => ({quote: item.quote.text, relation: item.relation, selector: path(item.node)})),
    warningScanLimited: strategy.length > 30,
    claimDominant: dominant(benefit), warningDominant: dominant(warning?.node),
    legal: legalData, label: label ? measure(label, null) : null
  };
}
