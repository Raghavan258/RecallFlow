import { evidenceForSelection } from "../graph/evidence";
import type { GraphNode, MemoryDetail } from "../types";

/** Original messages that support the selected memory or message node. */
export function EvidencePanel({
  node,
  memory,
  loading,
  error,
  onShowSources,
}: {
  node: GraphNode | null;
  memory: MemoryDetail | null;
  loading: boolean;
  error: string | null;
  onShowSources: (messageIds: string[]) => void;
}) {
  const shown = evidenceForSelection(memory, node?.type === "memory" || node?.type === "decision" ? node.id : null);
  return (
    <section className="panel">
      <h2 className="panel-title">Source evidence</h2>
      {loading ? <p className="text-sm text-stone-600">Loading source messages…</p> : null}
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {!loading && node === null ? <p className="text-sm text-stone-600">Choose a memory to see the original messages behind it.</p> : null}
      {shown ? <MemoryEvidence memory={shown} onShowSources={onShowSources} /> : null}
      {!memory && node?.type === "message" ? <MessageCard node={node} /> : null}
    </section>
  );
}

function MemoryEvidence({ memory, onShowSources }: { memory: MemoryDetail; onShowSources: (messageIds: string[]) => void }) {
  return (
    <div className="space-y-3">
      <p className="text-sm leading-6 text-ink">{memory.text}</p>
      <button type="button" className="button-secondary" onClick={() => onShowSources(memory.source_messages.map((item) => item.id))}>
        Show messages on graph
      </button>
      <ul className="space-y-2">
        {memory.source_messages.map((message) => (
          <li key={message.id} className="evidence-card">
            <EvidenceMeta speaker={message.speaker} position={message.position} timestamp={message.timestamp} sourceId={message.source_id} />
            <p className="mt-1 text-sm leading-6">{message.content}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MessageCard({ node }: { node: GraphNode }) {
  const speaker = String(node.payload.speaker ?? "Unknown speaker");
  const content = String(node.payload.content ?? node.label);
  const timestamp = typeof node.payload.timestamp === "string" ? node.payload.timestamp : null;
  const sourceId = typeof node.payload.source_id === "string" ? node.payload.source_id : null;
  const position = typeof node.payload.position === "number" ? node.payload.position : 0;
  return (
    <article className="evidence-card">
      <EvidenceMeta speaker={speaker} position={position} timestamp={timestamp} sourceId={sourceId} />
      <p className="mt-1 text-sm leading-6">{content}</p>
    </article>
  );
}

function EvidenceMeta({
  speaker,
  position,
  timestamp,
  sourceId,
}: {
  speaker: string;
  position: number;
  timestamp: string | null;
  sourceId: string | null;
}) {
  return (
    <p className="text-xs text-stone-500">
      {speaker} · message {position + 1} · {timestamp ?? "No timestamp provided"} · {sourceId ?? "No source id provided"}
    </p>
  );
}
