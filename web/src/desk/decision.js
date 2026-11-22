// Szkic opiera się wyłącznie na danych sprawy. Analityk musi go sprawdzić i zatwierdzić.
const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
const limit = (value, max) => {
  const text = clean(value);
  return text.length <= max ? text : `${text.slice(0, max - 1).replace(/[\uD800-\uDBFF]$/, "")}…`;
};
export function hasOwnExplanation(before, after) {
  const a = clean(before);
  const b = clean(after);
  if (a === b) return false;
  let start = 0;
  while (start < a.length && start < b.length && a[start] === b[start]) start++;
  let end = 0;
  while (end < a.length - start && end < b.length - start && a[a.length - 1 - end] === b[b.length - 1 - end]) end++;
  return b.slice(start, b.length - end).trim().length >= 8;
}
const counterOf = (c) => c.counter?.find((e) => e.counterKind !== "neutral_context" && e.text && e.effect);
export const needsOwnReason = (c, resolution) => ["no_signal", "close", "control_result", "data_received", "reopen"].includes(resolution);

export function decisionDraft(c, resolution) {
  const counter = counterOf(c);
  const claim = c.evidence?.find((e) => e.id === c.claim?.evidenceId && e.text)
    || c.evidence?.find((e) => e.role === "claim" && e.text);
  const reason = c.reasons?.find((r) => !/^możliwe niewinne wyjaśnienie/i.test(r)) || c.reason;
  const check = c.checks?.find((item) => item.state === "przesłanka" && (item.quote || item.evidence || item.summary));
  const observation = limit(reason || (check && `${check.label}: ${check.quote || check.evidence || check.summary}`), 700);
  const evidence = limit(claim?.text || check?.quote, 500);
  const uncertainty = limit(c.missing?.length ? `Brakujące dane: ${c.missing.join(", ")}.` : c.alternative, 500);
  const action = {
    refer_to_control: "Proponuję przekazać sprawę do kontroli.",
    complete_data: "Proponuję uzupełnić dane przed dalszą oceną.",
    no_signal: "Podaj powód zakończenia bez przesłanki i wskaż jego podstawę.",
    close: "Podaj powód zakończenia sprawy.",
    control_result: "Opisz ustalenie kontroli i jego podstawę lub źródło (np. wpis w wykazie albo czas wypowiedzi).",
    data_received: "Opisz, co ustalono lub otrzymano, oraz podaj źródło lub link (np. wpis w wykazie albo czas wypowiedzi).",
    reopen: "Podaj powód ponownego otwarcia.",
  }[resolution] || "";
  const support = resolution === "no_signal" && counter
    ? `Fragment do weryfikacji: „${limit(counter.text, 500)}”. Sprawdź, czy dotyczy tej relacji i podaj źródło.`
    : observation && `Ustalenie: ${observation}`;
  const quote = resolution !== "no_signal" && evidence && !observation.includes(evidence) && `Fragment materiału: „${evidence}”.`;
  const rawSource = resolution === "no_signal" && counter ? counter.link || counter.url : claim?.link || c.url;
  const source = /^https?:\/\//i.test(String(rawSource || "")) ? `Źródło: ${limit(rawSource, 250)}` : null;
  const draft = [action, support, quote, source, uncertainty && `Niepewność: ${uncertainty}`].filter(Boolean).join("\n\n");
  return draft.length <= 2000 ? draft : `${draft.slice(0, 1999).replace(/[\uD800-\uDBFF]$/, "")}…`;
}
