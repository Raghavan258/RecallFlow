import type { Graph, GraphNode, Topic } from "../types";

/** Details for the selected graph node. */
export function DetailsPanel({ graph, node, topics }: { graph: Graph | null; node: GraphNode | null; topics: Topic[] }) {
  return (
    <section className="panel">
      <h2 className="panel-title">Details</h2>
      {node === null ? <p className="text-sm text-stone-600">Select a node to inspect its text, topics, and links.</p> : null}
      {node ? <NodeDetail graph={graph} node={node} topics={topics} /> : null}
    </section>
  );
}

function NodeDetail({ graph, node, topics }: { graph: Graph | null; node: GraphNode; topics: Topic[] }) {
  const text = typeof node.payload.text === "string" ? node.payload.text : node.label;
  const summary = typeof node.payload.summary === "string" ? node.payload.summary : "";
  const linked = topics.filter((topic) => node.topic_ids.includes(topic.id) || topic.id === node.id);
  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs tracking-wide text-teal uppercase">{node.type}</p>
      <p className="leading-6 text-ink">{text}</p>
      {summary ? <p className="text-stone-600">{summary}</p> : null}
      <KeywordList node={node} />
      {linked.length > 0 ? <p className="text-stone-600">Topics: {linked.map((topic) => topic.label).join(", ")}</p> : null}
      <RelationshipList graph={graph} nodeId={node.id} />
    </div>
  );
}

function KeywordList({ node }: { node: GraphNode }) {
  const keywords = Array.isArray(node.payload.keywords) ? node.payload.keywords.map(String) : [];
  if (keywords.length === 0) {
    return null;
  }
  return <p className="text-stone-600">Keywords: {keywords.join(", ")}</p>;
}

function RelationshipList({ graph, nodeId }: { graph: Graph | null; nodeId: string }) {
  const edges = (graph?.edges ?? []).filter((edge) => edge.source === nodeId || edge.target === nodeId);
  if (edges.length === 0) {
    return <p className="text-stone-500">No stored relationships for this node.</p>;
  }
  return (
    <ul className="space-y-1">
      {edges.slice(0, 8).map((edge) => (
        <li key={edge.id} className="rounded-xl bg-paper px-2 py-1 text-xs">
          {edge.type}
          {edge.source === nodeId ? " →" : " ←"} {edge.target === nodeId ? edge.source_type : edge.target_type}
        </li>
      ))}
    </ul>
  );
}
