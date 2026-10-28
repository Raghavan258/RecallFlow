import { Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useRef } from "react";

import { toFlowEdges, toFlowNodes } from "../graph/flow";
import { placeNodes, type Point } from "../graph/layout";
import { visibleNodeIds } from "../graph/visibility";
import type { Graph } from "../types";
import { nodeTypes } from "./nodeTypes";
import { StateMessage } from "./StateMessage";

interface CanvasProps {
  graph: Graph | null;
  search: string;
  topicIds: ReadonlySet<string> | null;
  expanded: readonly string[];
  sourceMessageIds: readonly string[];
  conversationSelected: boolean;
  selectedId: string | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}

/** Interactive graph with zoom, pan, search, and expandable topics. */
export function GraphCanvas(props: CanvasProps) {
  return (
    <div className="relative min-h-[560px] flex-1 overflow-hidden rounded-2xl border border-line bg-[#f7f4ec]">
      {props.busy ? <p className="absolute top-3 left-3 z-10 rounded-full bg-white px-3 py-1 text-xs shadow">Working…</p> : null}
      <ReactFlowProvider>
        <CanvasBody {...props} />
      </ReactFlowProvider>
    </div>
  );
}

function CanvasBody(props: CanvasProps) {
  const positions = useRef(new Map<string, Point>());
  const conversationId = props.graph?.conversation_id ?? "";
  const seenConversation = useRef(conversationId);
  if (seenConversation.current !== conversationId) {
    seenConversation.current = conversationId;
    positions.current.clear();
  }
  const model = useMemo(() => buildModel(props, positions.current), [props]);
  if (!props.graph) {
    if (props.busy) {
      return <StateMessage title="Loading conversation" body="Fetching the stored graph." />;
    }
    if (props.conversationSelected) {
      return <StateMessage title="Graph unavailable" body="The latest graph could not be shown. The error above has the reason." />;
    }
    return <StateMessage title="No conversation yet" body="Paste a transcript, import JSON, or load the sample conversation." />;
  }
  if (props.graph.nodes.length === 0) {
    return <StateMessage title="Nothing extracted yet" body="Run extraction to build topics, memories, and relationships from the original messages." />;
  }
  if (model.nodes.length === 0) {
    return <StateMessage title="No matching nodes" body="Clear the search or topic filter to see the topic clusters again." />;
  }
  return (
    <ReactFlow
      nodes={model.nodes}
      edges={model.edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_event, node) => props.onSelect(node.id)}
      onNodeDragStop={(_event, node) => positions.current.set(node.id, node.position)}
      fitView
      minZoom={0.2}
    >
      <FitOnChange token={model.token} />
      <Background gap={18} color="#e4dccb" />
      <Controls />
      <MiniMap pannable zoomable />
    </ReactFlow>
  );
}

function buildModel(props: CanvasProps, previous: Map<string, Point>) {
  const graph = props.graph;
  if (!graph) {
    return { nodes: [], edges: [], token: "empty" };
  }
  const expanded = new Set(props.expanded);
  const visible = visibleNodeIds(graph.nodes, {
    search: props.search,
    acceptedTopicIds: props.topicIds,
    expanded,
    sourceMessageIds: props.sourceMessageIds,
  });
  const placed = placeNodes(graph.nodes, visible, previous);
  previous.clear();
  for (const [id, point] of placed) {
    previous.set(id, point);
  }
  const nodes = toFlowNodes(graph.nodes, visible, placed, expanded, props.selectedId, props.onToggle, props.onSelect);
  const edges = toFlowEdges(graph, visible, props.selectedId);
  return { nodes, edges, token: `${graph.extraction_run_id}:${[...visible].sort().join(",")}` };
}

function FitOnChange({ token }: { token: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const frame = requestAnimationFrame(() => fitView({ padding: 0.18, duration: 200 }));
    return () => cancelAnimationFrame(frame);
  }, [token, fitView]);
  return null;
}
