import { useState } from "react";

import type { ConversationSummary } from "../types";

type ImportMode = "paste" | "json";

/** Paste or JSON import, plus the sample conversation action. */
export function ImportPanel({
  conversations,
  selectedId,
  busy,
  onSelect,
  onImport,
  onSample,
  onExtract,
}: {
  conversations: ConversationSummary[];
  selectedId: string | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onImport: (mode: ImportMode, title: string, text: string) => void;
  onSample: () => void;
  onExtract: () => void;
}) {
  const [mode, setMode] = useState<ImportMode>("paste");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  return (
    <section className="panel">
      <h2 className="panel-title">Import</h2>
      <ConversationSelect conversations={conversations} selectedId={selectedId} onSelect={onSelect} />
      <ModeSwitch mode={mode} onChange={setMode} />
      <label className="field">
        Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional title" />
      </label>
      <label className="field">
        {mode === "paste" ? "Transcript" : "JSON conversation"}
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={7}
          placeholder={mode === "paste" ? "Ava: We decided to ship onboarding in three steps." : '{"messages":[{"speaker":"Ava","content":"..."}]}'}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="button-primary" disabled={busy || !text.trim()} onClick={() => onImport(mode, title, text)}>
          Import and extract
        </button>
        <button type="button" className="button-secondary" disabled={busy || !selectedId} onClick={onExtract}>
          Extract
        </button>
        <button type="button" className="button-secondary" disabled={busy} onClick={onSample}>
          Load sample
        </button>
      </div>
    </section>
  );
}

function ConversationSelect({
  conversations,
  selectedId,
  onSelect,
}: {
  conversations: ConversationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <label className="field">
      Stored conversations
      <select value={selectedId ?? ""} onChange={(event) => onSelect(event.target.value)}>
        <option value="">None selected</option>
        {conversations.map((item) => (
          <option key={item.id} value={item.id}>
            {item.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function ModeSwitch({ mode, onChange }: { mode: ImportMode; onChange: (mode: ImportMode) => void }) {
  return (
    <div className="mb-3 flex gap-2">
      <button type="button" className={mode === "paste" ? "chip chip-active" : "chip"} onClick={() => onChange("paste")}>
        Paste
      </button>
      <button type="button" className={mode === "json" ? "chip chip-active" : "chip"} onClick={() => onChange("json")}>
        JSON
      </button>
    </div>
  );
}
