// Import ręczny: zapisana strona Biblioteki Reklam Meta albo profilu Instagram → POST /v1/import/meta (surowy plik).
// Pokazuje wynik {ads, posts, new, existing, warnings} oraz komunikaty błędów z `detail` (413, 415, 422); 202 = czeka na worker.
import React, { useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { FileInput } from "@astryxdesign/core/FileInput";
import { VStack } from "@astryxdesign/core/Layout";
import { Heading, Text } from "@astryxdesign/core/Text";
import { api } from "./api.js";

const plural = (n, one, few, many) => (n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

export function MetaImport({ onDone, headingLevel = 2 }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  async function submit() {
    if (busy) return;
    if (!file) {
      setResult({ status: "warning", title: "Wybierz zapisany plik .html, .htm lub .txt." });
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const r = await api.importMeta(file);
      const parts = [r.ads ? `${r.ads} ${plural(r.ads, "reklama", "reklamy", "reklam")}` : null, r.posts ? `${r.posts} ${plural(r.posts, "post", "posty", "postów")}` : null].filter(Boolean).join(", ") || "brak wpisów";
      const waiting = r.scan?.status === "queued";
      setResult({
        status: waiting ? "info" : r.alreadyImported ? "info" : "success",
        title: waiting ? `Plik zapisany (${parts}); analiza czeka w kolejce.` : r.alreadyImported ? `Ten plik był już wczytany (${parts}); nic nie dodano.` : `Wczytano: ${parts}. Nowych: ${r.new ?? 0}, już w bazie: ${r.existing ?? 0}.`,
        description: [waiting ? "Wpisy pojawią się na liście, gdy analiza się skończy." : "Wpisy są na liście Do sprawdzenia (stan Wszystkie, M2) z plakietką „import ręczny”.", ...(r.warnings || [])].join(" "),
      });
      onDone?.();
    } catch (e) {
      setResult({ status: "error", title: "Nie wczytano pliku", description: e.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <VStack gap={2}>
      <Heading level={headingLevel + 1}>Zapisana strona Biblioteki Reklam Meta lub profilu Instagram</Heading>
      <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Jak zapisać stronę</Text>}>
        <VStack gap={0.5} role="list" aria-label="Jak zapisać stronę" padding={1}>
          <Text role="listitem">1. Otwórz w przeglądarce Bibliotekę Reklam Meta albo profil na Instagramie i przewiń, aż załadują się wpisy.</Text>
          <Text role="listitem">2. Zapisz stronę: Ctrl+S (Cmd+S), „Strona internetowa, tylko HTML”. Może być też skopiowana treść w pliku .txt.</Text>
          <Text role="listitem">3. Wybierz zapisany plik i wgraj. Plik nie jest otwierany ani wykonywany; czyta się z niego tylko tekst.</Text>
        </VStack>
      </Collapsible>
      <FileInput label="Zapisana strona (.html, .htm, .txt)" mode="dropzone" placeholder="Wybierz zapisany plik" value={file} onChange={setFile}
        description="Limit 25 MiB" maxSize={25 * 1024 * 1024} accept=".html,.htm,.txt,text/html,text/plain" />
      {result && <Banner status={result.status} title={result.title} description={result.description} />}
      <Button label="Wgraj do analizy" variant="primary" isLoading={busy} onClick={submit} />
    </VStack>
  );
}
