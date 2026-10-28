import type { GraphNode } from "../types";

/** Topic parent link used to expand a filter to descendant clusters. */
export interface TopicLink {
  id: string;
  parent_id: string | null;
}

/** Filters that decide which graph nodes are on screen. */
export interface GraphFilters {
  search: string;
  acceptedTopicIds: ReadonlySet<string> | null;
  expanded: ReadonlySet<string>;
  sourceMessageIds: readonly string[];
}

/**
 * Topic ids covered by a parent filter, including the selected topic and its descendants.
 * A null selection means no topic filter is active.
 */
export function acceptedTopicIds(topics: readonly TopicLink[], selectedId: string | null): ReadonlySet<string> | null {
  if (!selectedId) {
    return null;
  }
  const children = childIndex(topics);
  const accepted = new Set<string>([selectedId]);
  const pending = [selectedId];
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current) {
      continue;
    }
    for (const child of children.get(current) ?? []) {
      if (!accepted.has(child)) {
        accepted.add(child);
        pending.push(child);
      }
    }
  }
  return accepted;
}

/**
 * Choose nodes for the current search, topic filter, and expanded clusters.
 * Search reveals matches even when their topic cluster is collapsed.
 * Requested source messages stay visible even when search does not match them.
 */
export function visibleNodeIds(nodes: GraphNode[], filters: GraphFilters): Set<string> {
  const query = filters.search.trim().toLowerCase();
  return new Set(nodes.filter((node) => isVisible(node, filters, query)).map((node) => node.id));
}

function childIndex(topics: readonly TopicLink[]): Map<string, string[]> {
  const children = new Map<string, string[]>();
  for (const topic of topics) {
    if (!topic.parent_id) {
      continue;
    }
    const siblings = children.get(topic.parent_id) ?? [];
    siblings.push(topic.id);
    children.set(topic.parent_id, siblings);
  }
  return children;
}

function isVisible(node: GraphNode, filters: GraphFilters, query: string): boolean {
  if (node.type === "message") {
    return filters.sourceMessageIds.includes(node.id);
  }
  if (!matchesQuery(node, query)) {
    return false;
  }
  if (filters.acceptedTopicIds && !belongsToTopics(node, filters.acceptedTopicIds)) {
    return false;
  }
  if (query || filters.acceptedTopicIds) {
    return true;
  }
  if (node.initially_visible) {
    return true;
  }
  return node.topic_ids.some((topicId) => filters.expanded.has(topicId));
}

function matchesQuery(node: GraphNode, query: string): boolean {
  return query.length === 0 || searchText(node).includes(query);
}

function belongsToTopics(node: GraphNode, accepted: ReadonlySet<string>): boolean {
  return accepted.has(node.id) || node.topic_ids.some((topicId) => accepted.has(topicId));
}

function searchText(node: GraphNode): string {
  const payload = Object.values(node.payload)
    .filter((value) => typeof value === "string")
    .join(" ");
  return `${node.label} ${node.type} ${payload}`.toLowerCase();
}
