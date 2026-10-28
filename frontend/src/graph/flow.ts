import type { Edge, Node } from "@xyflow/react";

import type { Graph, GraphNode } from "../types";
import type { Point } from "./layout";

const EDGE_COLORS: Record<string, string> = {
  CONTAINS: "#0e6e6b",
  RELATED_TO: "#8a7348",
  MENTIONS: "#5c4d7a",
  SUPPORTS: "#1e4d8c",
  DEPENDS_ON: "#9a4d1c",
  SUPERSEDES: "#6b3f1d",
  CONTRADICTS: "#9b2335",
  DERIVED_FROM: "#6b6258",
};

/** Data passed into the custom graph node. */
export interface RecordData extends Record<string, unknown> {
  kind: string;
  label: string;
  expandable: boolean;
  expanded: boolean;
  onToggle: () => void;
  onOpen: () => void;
}

/**
 * Convert visible API nodes into React Flow nodes.
 */
export function toFlowNodes(
  nodes: GraphNode[],
  visible: ReadonlySet<string>,
  positions: ReadonlyMap<string, Point>,
  expanded: ReadonlySet<string>,
  selectedId: string | null,
  onToggle: (id: string) => void,
  onOpen: (id: string) => void,
): Node<RecordData>[] {
  return nodes
    .filter((node) => visible.has(node.id))
    .map((node) => toFlowNode(node, positions, expanded, selectedId, onToggle, onOpen));
}

/**
 * Keep edges whose endpoints are both visible and style the selected neighborhood.
 */
export function toFlowEdges(graph: Graph, visible: ReadonlySet<string>, selectedId: string | null): Edge[] {
  return graph.edges
    .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
    .map((edge) => toFlowEdge(edge, selectedId));
}

function toFlowNode(
  node: GraphNode,
  positions: ReadonlyMap<string, Point>,
  expanded: ReadonlySet<string>,
  selectedId: string | null,
  onToggle: (id: string) => void,
  onOpen: (id: string) => void,
): Node<RecordData> {
  return {
    id: node.id,
    type: "record",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    selected: node.id === selectedId,
    data: {
      kind: node.type,
      label: node.label,
      expandable: node.type === "topic" || node.type === "subtopic",
      expanded: expanded.has(node.id),
      onToggle: () => onToggle(node.id),
      onOpen: () => onOpen(node.id),
    },
  };
}

function toFlowEdge(edge: Graph["edges"][number], selectedId: string | null): Edge {
  const active = selectedId !== null && (edge.source === selectedId || edge.target === selectedId);
  const dimmed = selectedId !== null && !active;
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.type,
    animated: active,
    style: {
      stroke: EDGE_COLORS[edge.type] ?? "#6b6258",
      strokeWidth: active ? 2.4 : 1.2,
      opacity: dimmed ? 0.18 : 0.9,
    },
    labelStyle: { fill: "#1b2430", fontSize: 10 },
  };
}
