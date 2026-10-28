import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RetrievalResult } from "../types";
import { RetrievalPanel } from "./RetrievalPanel";

function result(): RetrievalResult {
  return {
    conversation_id: "c1",
    extraction_run_id: "run-1",
    question: "When is the greenhouse tomato schedule?",
    mode: "graph",
    topics: ["Greenhouse"],
    token_usage: { budget: 180, selected: 8, discarded: 0 },
    latency_ms: 1,
    evidence: [
      {
        memory_id: "mem-1",
        text: "The greenhouse tomato schedule is Monday and Thursday.",
        topic_ids: ["topic-1"],
        topic_labels: ["Greenhouse"],
        source_message_ids: ["msg-1"],
        source_ids: ["m1"],
        score: 0.5,
        explanation: "Shared terms: greenhouse, tomato.",
        selected: true,
        sources: [],
      },
    ],
  };
}

describe("RetrievalPanel", () => {
  it("shows the score, source id, and explanation for a selected memory", () => {
    render(
      <RetrievalPanel
        disabled={false}
        loading={false}
        error={null}
        result={result()}
        onAsk={() => undefined}
        onShowSources={() => undefined}
      />,
    );
    expect(screen.getByText("Score 0.50 · Sources m1")).toBeTruthy();
    expect(screen.getByText("Shared terms: greenhouse, tomato.")).toBeTruthy();
  });
});
