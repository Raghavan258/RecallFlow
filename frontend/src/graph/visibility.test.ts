import { describe, expect, it } from "vitest";

import type { GraphNode } from "../types";
import { evidenceForSelection } from "./evidence";
import { acceptedTopicIds, visibleNodeIds } from "./visibility";

const message: GraphNode = {
  id: "m1",
  type: "message",
  label: "Ava: notes",
  initially_visible: false,
  topic_ids: [],
  payload: { content: "notes about the launch" },
};

const parent: GraphNode = {
  id: "parent",
  type: "topic",
  label: "Launch",
  initially_visible: true,
  topic_ids: ["parent"],
  payload: {},
};

const child: GraphNode = {
  id: "child",
  type: "subtopic",
  label: "Timeline",
  initially_visible: false,
  topic_ids: ["parent"],
  payload: {},
};

const descendantMemory: GraphNode = {
  id: "mem-child",
  type: "memory",
  label: "The launch timeline is May.",
  initially_visible: false,
  topic_ids: ["child"],
  payload: { text: "The launch timeline is May." },
};

describe("visibleNodeIds", () => {
  it("keeps requested source messages visible when search does not match", () => {
    const visible = visibleNodeIds([message, parent], {
      search: "pricing",
      acceptedTopicIds: null,
      expanded: new Set(),
      sourceMessageIds: ["m1"],
    });
    expect(visible.has("m1")).toBe(true);
    expect(visible.has("parent")).toBe(false);
  });

  it("includes descendant memories when a parent topic is selected", () => {
    const topics = [
      { id: "parent", parent_id: null },
      { id: "child", parent_id: "parent" },
    ];
    const visible = visibleNodeIds([parent, child, descendantMemory], {
      search: "",
      acceptedTopicIds: acceptedTopicIds(topics, "parent"),
      expanded: new Set(),
      sourceMessageIds: [],
    });
    expect(visible.has("parent")).toBe(true);
    expect(visible.has("child")).toBe(true);
    expect(visible.has("mem-child")).toBe(true);
  });
});

describe("evidenceForSelection", () => {
  it("drops evidence that does not belong to the selected memory", () => {
    const stale = { id: "mem-a" };
    expect(evidenceForSelection(stale, "mem-b")).toBeNull();
    expect(evidenceForSelection(stale, null)).toBeNull();
    expect(evidenceForSelection(stale, "mem-a")).toBe(stale);
  });
});
