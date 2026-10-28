import type {
  ConversationDetail,
  ConversationList,
  Graph,
  ImportRequest,
  MemoryDetail,
  RetrievalResult,
  Topic,
} from "../types";
import type { RetrievalQuery } from "../retrieval/request";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Call the RecallFlow API and return JSON, or throw a readable error.
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return (await response.json()) as T;
}

/** List conversations and dashboard counts. */
export function listConversations(): Promise<ConversationList> {
  return request<ConversationList>("/api/conversations");
}

/** Store a transcript or JSON conversation. */
export function importConversation(payload: ImportRequest): Promise<ConversationDetail> {
  return request<ConversationDetail>("/api/conversations/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Run extraction and return the resulting graph. */
export function extractConversation(conversationId: string): Promise<Graph> {
  return request<Graph>(`/api/conversations/${conversationId}/extract`, { method: "POST" });
}

/** Read the latest graph for a conversation. */
export function getGraph(conversationId: string): Promise<Graph> {
  return request<Graph>(`/api/conversations/${conversationId}/graph`);
}

/** Read topics, optionally for one conversation. */
export function getTopics(conversationId: string): Promise<Topic[]> {
  return request<Topic[]>(`/api/topics?conversation_id=${encodeURIComponent(conversationId)}`);
}

/** Read one memory and its source messages. */
export function getMemory(memoryId: string): Promise<MemoryDetail> {
  return request<MemoryDetail>(`/api/memories/${memoryId}`);
}

/** Rank stored memories for a question. The response is evidence, not an answer. */
export function retrieveConversation(conversationId: string, query: RetrievalQuery): Promise<RetrievalResult> {
  return request<RetrievalResult>(`/api/conversations/${conversationId}/retrieve`, {
    method: "POST",
    body: JSON.stringify(query),
  });
}

/** Load the bundled sample conversation. */
export function getSample(): Promise<ImportRequest> {
  return request<ImportRequest>("/api/sample/conversation");
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    return `Request failed (${response.status}).`;
  }
  return `Request failed (${response.status}).`;
}
