import { useState } from "react";

import type { RetrievalMode } from "../retrieval/request";
import type { RetrievalResult } from "../types";

/** Ask a question and inspect retrieved memories without leaving the graph. */
export function RetrievalPanel({
  disabled,
  loading,
  error,
  result,
  onAsk,
  onShowSources,
}: {
  disabled: boolean;
  loading: boolean;
  error: string | null;
  result: RetrievalResult | null;
  onAsk: (question: string, mode: RetrievalMode, tokenBudget: number) => void;
  onShowSources: (messageIds: string[]) => void;
}) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("graph");
  const [budget, setBudget] = useState(180);
  return (
    <section className="panel">
      <h2 className="panel-title">Retrieve</h2>
      <label className="field">
        Question
        <textarea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="When is the greenhouse tomato schedule?" />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="field">
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as RetrievalMode)}>
            <option value="keyword">Keyword</option>
            <option value="graph">Graph</option>
            <option value="budget">Graph + budget</option>
          </select>
        </label>
        <label className="field">
          Token budget
          <input type="number" min={0} value={budget} onChange={(event) => setBudget(Number(event.target.value))} />
        </label>
      </div>
      <button type="button" className="button-primary" disabled={disabled || loading || !question.trim()} onClick={() => onAsk(question, mode, budget)}>
        {loading ? "Retrieving…" : "Retrieve evidence"}
      </button>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      {result ? <ResultList result={result} onShowSources={onShowSources} /> : null}
    </section>
  );
}

function ResultList({ result, onShowSources }: { result: RetrievalResult; onShowSources: (messageIds: string[]) => void }) {
  const visible = result.evidence.filter((item) => item.selected);
  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs text-stone-600">
        {result.token_usage.selected} tokens selected, {result.token_usage.discarded} discarded, {result.latency_ms} ms
      </p>
      {visible.length === 0 ? <p className="text-sm text-stone-600">No stored memory matched this question.</p> : null}
      {visible.map((item) => (
        <article key={item.memory_id} className="evidence-card">
          <p className="text-sm leading-6">{item.text}</p>
          <p className="mt-1 text-xs text-stone-500">
            Score {item.score.toFixed(2)} · Sources {item.source_ids.join(", ") || "none"}
          </p>
          <p className="mt-1 text-xs text-stone-600">{item.explanation}</p>
          <button type="button" className="button-secondary mt-2" onClick={() => onShowSources(item.source_message_ids)}>
            Show messages on graph
          </button>
        </article>
      ))}
    </div>
  );
}
