import { useEffect, useState } from "react";

import { retrieveConversation } from "../api/client";
import type { RetrievalMode } from "../retrieval/request";
import { retrievalQuery } from "../retrieval/request";
import type { RetrievalResult } from "../types";

/** Question box state. It does not replace the open graph. */
export function useRetrieval(selectedId: string | null) {
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, [selectedId]);
  return {
    result,
    error,
    loading,
    ask: (question: string, mode: RetrievalMode, tokenBudget: number) => ask(selectedId, question, mode, tokenBudget, setResult, setError, setLoading, loading),
  };
}

async function ask(
  selectedId: string | null,
  question: string,
  mode: RetrievalMode,
  tokenBudget: number,
  setResult: (value: RetrievalResult | null) => void,
  setError: (value: string | null) => void,
  setLoading: (value: boolean) => void,
  loading: boolean,
) {
  const trimmed = question.trim();
  if (!selectedId || !trimmed || loading) {
    return;
  }
  setLoading(true);
  setError(null);
  try {
    setResult(await retrieveConversation(selectedId, retrievalQuery(trimmed, mode, tokenBudget)));
  } catch (caught) {
    setResult(null);
    setError(caught instanceof Error ? caught.message : "Unexpected error.");
  } finally {
    setLoading(false);
  }
}
