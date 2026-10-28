/** Retrieval modes accepted by the API. */
export type RetrievalMode = "keyword" | "graph" | "budget";

/** Body sent to the retrieval endpoint. Answers are never included. */
export interface RetrievalQuery {
  question: string;
  mode: RetrievalMode;
  token_budget: number;
  limit: number;
}

/**
 * Build a retrieval request. Blank questions are rejected by the caller.
 */
export function retrievalQuery(question: string, mode: RetrievalMode, tokenBudget: number): RetrievalQuery {
  return {
    question: question.trim(),
    mode,
    token_budget: tokenBudget,
    limit: 5,
  };
}
