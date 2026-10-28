/** Original message preserved by the API. */
export interface Message {
  id: string;
  source_id: string | null;
  speaker: string;
  content: string;
  position: number;
  timestamp: string | null;
}

/** Conversation row with counts from the latest extraction. */
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
  topic_count: number;
  memory_count: number;
  relationship_count: number;
  provider: string | null;
}

/** Dashboard totals across latest extraction runs. */
export interface Counts {
  conversations: number;
  topics: number;
  memories: number;
  relationships: number;
}

/** Conversation index response. */
export interface ConversationList {
  items: ConversationSummary[];
  totals: Counts;
}

/** Imported conversation and its original messages. */
export interface ConversationDetail {
  id: string;
  title: string;
  source_format: string;
  created_at: string;
  messages: Message[];
}

/** Topic shown in the sidebar. */
export interface Topic {
  id: string;
  conversation_id: string;
  parent_id: string | null;
  label: string;
  keywords: string[];
  summary: string;
  memory_count: number;
}

/** Node returned by the graph endpoint. */
export interface GraphNode {
  id: string;
  type: string;
  label: string;
  initially_visible: boolean;
  topic_ids: string[];
  payload: Record<string, unknown>;
}

/** Relationship projected as an edge. */
export interface GraphEdge {
  id: string;
  type: string;
  source: string;
  target: string;
  source_type: string;
  target_type: string;
  evidence_message_ids: string[];
}

/** Graph for the latest extraction run. */
export interface Graph {
  conversation_id: string;
  extraction_run_id: string | null;
  provider: string | null;
  limitations: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Topic reference nested on a memory. */
export interface TopicBrief {
  id: string;
  label: string;
  parent_id: string | null;
}

/** Relationship touching a selected memory. */
export interface MemoryRelationship {
  id: string;
  type: string;
  direction: string;
  other_type: string;
  other_id: string;
  other_label: string;
}

/** Memory plus the messages that support it. */
export interface MemoryDetail {
  id: string;
  conversation_id: string;
  extraction_run_id: string;
  provider: string;
  kind: string;
  text: string;
  confidence: number | null;
  topics: TopicBrief[];
  source_messages: Message[];
  relationships: MemoryRelationship[];
}

/** One ranked memory returned by retrieval. */
export interface RetrievalEvidence {
  memory_id: string;
  text: string;
  topic_ids: string[];
  topic_labels: string[];
  source_message_ids: string[];
  source_ids: string[];
  score: number;
  explanation: string;
  selected: boolean;
  sources: Message[];
}

/** Evidence package for a question. This is not an answer. */
export interface RetrievalResult {
  conversation_id: string;
  extraction_run_id: string;
  question: string;
  mode: string;
  evidence: RetrievalEvidence[];
  topics: string[];
  token_usage: { budget: number; selected: number; discarded: number };
  latency_ms: number;
}

/** Import body accepted by the API. */
export interface ImportRequest {
  title?: string;
  transcript?: string;
  messages?: Array<{
    speaker: string;
    content: string;
    source_id?: string;
    timestamp?: string;
  }>;
}
