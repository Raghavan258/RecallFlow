import { describe, expect, it } from "vitest";

import { retrievalQuery } from "./request";

describe("retrievalQuery", () => {
  it("sends the question, mode, and budget without an answer field", () => {
    const body = retrievalQuery("  When is the greenhouse tomato schedule? ", "budget", 40);
    expect(body).toEqual({
      question: "When is the greenhouse tomato schedule?",
      mode: "budget",
      token_budget: 40,
      limit: 5,
    });
    expect("answer" in body).toBe(false);
  });
});
