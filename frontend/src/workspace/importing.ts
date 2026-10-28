import type { ImportRequest } from "../types";

/**
 * Build an import payload from the paste box or a JSON document.
 * Missing titles are omitted so the API can apply its own default.
 */
export function buildImport(mode: "paste" | "json", title: string, text: string): ImportRequest {
  const trimmedTitle = title.trim();
  if (mode === "paste") {
    return trimmedTitle ? { title: trimmedTitle, transcript: text } : { transcript: text };
  }
  return withTitle(parseJson(text), trimmedTitle);
}

function parseJson(text: string): ImportRequest {
  let parsed: ImportRequest;
  try {
    parsed = JSON.parse(text) as ImportRequest;
  } catch {
    throw new Error("The JSON conversation could not be parsed.");
  }
  if (!parsed.messages && !parsed.transcript) {
    throw new Error("JSON must include messages or a transcript.");
  }
  return parsed;
}

function withTitle(payload: ImportRequest, title: string): ImportRequest {
  if (!title) {
    return payload;
  }
  return { ...payload, title };
}
