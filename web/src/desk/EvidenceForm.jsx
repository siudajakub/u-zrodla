import React, { useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { FileInput } from "@astryxdesign/core/FileInput";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Heading, Text } from "@astryxdesign/core/Text";
import { TextArea } from "@astryxdesign/core/TextArea";
import { TextInput } from "@astryxdesign/core/TextInput";
import { api } from "./api.js";

/** Własny plik audio lub wideo: trafia poza rzeczywiste kolejki, w stan „Demo” z oznaczeniem „plik operatora”. */
export function EvidenceForm({ onDone, onOpenDemo }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  async function submit() {
    if (busy) return;
    if (!file) {
      setResult({ status: "warning", title: "Wybierz plik audio lub wideo." });
      return;
    }
    setBusy(true);
    try {
      await api.uploadEvidence(file, title.trim(), description);
      setResult({ status: "success", title: "Plik przesłany do analizy.", description: "Po zakończeniu pojawi się na liście Do sprawdzenia, w stanie Demo, z oznaczeniem „plik operatora”." });
      onDone?.();
    } catch (e) {
      setResult({ status: "error", title: "Nie przesłano pliku", description: e.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <VStack gap={2}>
      <VStack gap={0.5}>
        <Heading level={3}>Nagranie lub plik własny</Heading>
        <Text type="supporting" color="secondary">Plik audio lub wideo (do 40 MiB, analiza do 120 sekund). Trafia poza rzeczywiste kolejki.</Text>
      </VStack>
      <FileInput label="Plik audio lub wideo" mode="dropzone" placeholder="Wybierz nagranie" value={file} onChange={setFile}
        description="mp4, wav, mp3, m4a, webm, ogg, mov, mkv, aac, flac" maxSize={40 * 1024 * 1024}
        accept="audio/*,video/*,.mp4,.wav,.mp3,.m4a,.webm,.ogg,.mov,.mkv,.aac,.flac" />
      <TextInput label="Tytuł" isOptional value={title} onChange={setTitle} htmlMaxLength={180} />
      <TextArea label="Opis" isOptional value={description} onChange={setDescription} htmlMaxLength={5000} />
      {result && <Banner status={result.status} title={result.title} description={result.description} />}
      <HStack gap={2} wrap="wrap">
        <Button label="Prześlij do analizy" variant="primary" isLoading={busy} onClick={submit} />
        <Button label="Zobacz stan Demo" variant="ghost" onClick={onOpenDemo} />
      </HStack>
    </VStack>
  );
}
