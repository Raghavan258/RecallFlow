import type { GraphNode } from "../types";

/** Canvas coordinate. */
export interface Point {
  x: number;
  y: number;
}

const ROOT_COLUMN = 320;
const ROOT_Y = 24;
const CHILD_START = 180;
const CHILD_GAP = 210;

/**
 * Place visible nodes. Existing positions are kept so dragging is not reset.
 */
export function placeNodes(
  nodes: GraphNode[],
  visible: ReadonlySet<string>,
  previous: ReadonlyMap<string, Point>,
): Map<string, Point> {
  const positions = new Map(previous);
  placeRoots(nodes, visible, positions);
  placeChildren(nodes, visible, positions);
  return positions;
}

function placeRoots(
  nodes: GraphNode[],
  visible: ReadonlySet<string>,
  positions: Map<string, Point>,
): void {
  const roots = nodes.filter((node) => node.type === "topic" && visible.has(node.id));
  roots.forEach((node, index) => {
    if (!positions.has(node.id)) {
      positions.set(node.id, { x: index * ROOT_COLUMN, y: ROOT_Y });
    }
  });
}

function placeChildren(
  nodes: GraphNode[],
  visible: ReadonlySet<string>,
  positions: Map<string, Point>,
): void {
  const groups = groupChildren(nodes, visible);
  for (const [parentId, children] of groups) {
    const origin = positions.get(parentId) ?? { x: 40, y: ROOT_Y };
    children.forEach((child, index) => {
      if (!positions.has(child.id)) {
        positions.set(child.id, { x: origin.x + 36, y: origin.y + CHILD_START + index * CHILD_GAP });
      }
    });
  }
}

function groupChildren(nodes: GraphNode[], visible: ReadonlySet<string>): Map<string, GraphNode[]> {
  const groups = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    if (!visible.has(node.id) || node.type === "topic") {
      continue;
    }
    const parentId = node.topic_ids[0] ?? "loose";
    const bucket = groups.get(parentId) ?? [];
    bucket.push(node);
    groups.set(parentId, bucket);
  }
  return groups;
}
