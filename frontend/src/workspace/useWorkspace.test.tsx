import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Graph, MemoryDetail } from "../types";
import { useWorkspace } from "./useWorkspace";

const api = vi.hoisted(() => ({
  listConversations: vi.fn(),
  getGraph: vi.fn(),
  getTopics: vi.fn(),
  getMemory: vi.fn(),
  extractConversation: vi.fn(),
  importConversation: vi.fn(),
  getSample: vi.fn(),
}));

vi.mock("../api/client", () => api);

function graph(): Graph {
  return {
    conversation_id: "c1",
    extraction_run_id: "run-1",
    provider: "baseline",
    limitations: [],
    nodes: [
      { id: "mem-a", type: "memory", label: "A", initially_visible: false, topic_ids: [], payload: { text: "A" } },
      { id: "mem-b", type: "memory", label: "B", initially_visible: false, topic_ids: [], payload: { text: "B" } },
    ],
    edges: [],
  };
}

function memory(id: string): MemoryDetail {
  return {
    id,
    conversation_id: "c1",
    extraction_run_id: "run-1",
    provider: "baseline",
    kind: "fact",
    text: id,
    confidence: 0.45,
    topics: [],
    source_messages: [],
    relationships: [],
  };
}

describe("useWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listConversations.mockResolvedValue({
      items: [
        {
          id: "c1",
          title: "Open",
          created_at: "2026-03-02T00:00:00+00:00",
          message_count: 1,
          topic_count: 0,
          memory_count: 2,
          relationship_count: 0,
          provider: "baseline",
        },
      ],
      totals: { conversations: 1, topics: 0, memories: 2, relationships: 0 },
    });
    api.getGraph.mockResolvedValue(graph());
    api.getTopics.mockResolvedValue([]);
  });

  it("clears evidence when the next memory request fails", async () => {
    api.getMemory.mockResolvedValueOnce(memory("mem-a")).mockRejectedValueOnce(new Error("missing"));
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.conversation_id).toBe("c1"));
    act(() => result.current.selectNode("mem-a"));
    await waitFor(() => expect(result.current.memory?.id).toBe("mem-a"));
    act(() => result.current.selectNode("mem-b"));
    await waitFor(() => expect(result.current.memoryError).toBe("missing"));
    expect(result.current.memory).toBeNull();
  });

  it("extracts the open conversation without importing another", async () => {
    api.extractConversation.mockResolvedValue(graph());
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.selectedId).toBe("c1"));
    await act(async () => {
      await result.current.extractSelected();
    });
    expect(api.extractConversation).toHaveBeenCalledTimes(1);
    expect(api.extractConversation).toHaveBeenCalledWith("c1");
    expect(api.importConversation).not.toHaveBeenCalled();
    expect(result.current.notice).toContain("latest run");
  });

  it("clears busy when a graph request is cancelled by selecting none", async () => {
    const first = deferred<Graph>();
    api.getGraph.mockReset();
    api.getGraph.mockImplementation(() => first.promise);
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.busy).toBe(true));
    act(() => result.current.selectConversation(""));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.graph).toBeNull();
    await act(async () => {
      first.resolve(graph());
    });
    expect(result.current.busy).toBe(false);
    expect(result.current.graph).toBeNull();
  });

  it("clears memory loading when focus moves to a topic", async () => {
    api.getTopics.mockResolvedValue([
      {
        id: "topic-1",
        conversation_id: "c1",
        parent_id: null,
        label: "Launch",
        keywords: ["launch"],
        summary: "Launch",
        memory_count: 1,
      },
    ]);
    const pending = deferred<MemoryDetail>();
    api.getMemory.mockImplementation(() => pending.promise);
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.topics).toHaveLength(1));
    act(() => result.current.selectNode("mem-a"));
    await waitFor(() => expect(result.current.memoryLoading).toBe(true));
    act(() => result.current.focusTopic("topic-1"));
    await waitFor(() => expect(result.current.memoryLoading).toBe(false));
    expect(result.current.memory).toBeNull();
    await act(async () => {
      pending.resolve(memory("mem-a"));
    });
    expect(result.current.memoryLoading).toBe(false);
    expect(result.current.memory).toBeNull();
  });

  it("ignores an older graph response after a newer request starts", async () => {
    const first = deferred<Graph>();
    const second = deferred<Graph>();
    api.getGraph.mockReset();
    api.getGraph.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.busy).toBe(true));
    act(() => result.current.selectConversation(""));
    await waitFor(() => expect(result.current.busy).toBe(false));
    act(() => result.current.selectConversation("c1"));
    await waitFor(() => expect(result.current.busy).toBe(true));
    const stale = { ...graph(), extraction_run_id: "stale" };
    await act(async () => {
      first.resolve(stale);
    });
    expect(result.current.busy).toBe(true);
    expect(result.current.graph).toBeNull();
    await act(async () => {
      second.resolve(graph());
    });
    await waitFor(() => expect(result.current.graph?.extraction_run_id).toBe("run-1"));
    expect(result.current.busy).toBe(false);
  });

  it("ignores an older memory response after a newer request starts", async () => {
    const first = deferred<MemoryDetail>();
    const second = deferred<MemoryDetail>();
    api.getMemory.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.nodes.length).toBe(2));
    act(() => result.current.selectNode("mem-a"));
    await waitFor(() => expect(result.current.memoryLoading).toBe(true));
    act(() => result.current.selectNode("mem-b"));
    await waitFor(() => expect(result.current.memoryLoading).toBe(true));
    await act(async () => {
      first.resolve(memory("mem-a"));
    });
    expect(result.current.memory).toBeNull();
    expect(result.current.memoryLoading).toBe(true);
    await act(async () => {
      second.resolve(memory("mem-b"));
    });
    await waitFor(() => expect(result.current.memory?.id).toBe("mem-b"));
    expect(result.current.memoryLoading).toBe(false);
  });

  it("keeps the previous graph when re-extraction fails", async () => {
    let release: (value: Graph) => void = () => undefined;
    api.extractConversation.mockImplementation(
      () =>
        new Promise<Graph>((resolve) => {
          release = resolve;
        }),
    );
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.nodes.length).toBe(2));
    let first: Promise<void> = Promise.resolve();
    let second: Promise<void> = Promise.resolve();
    act(() => {
      first = result.current.extractSelected();
      second = result.current.extractSelected();
    });
    await act(async () => {
      release(graph());
      await first;
      await second;
    });
    expect(api.extractConversation).toHaveBeenCalledTimes(1);

    api.extractConversation.mockRejectedValue(new Error("extract failed"));
    await act(async () => {
      await result.current.extractSelected();
    });
    expect(result.current.graph?.extraction_run_id).toBe("run-1");
    expect(result.current.error).toBe("extract failed");
    expect(result.current.selectedId).toBe("c1");
    expect(result.current.busy).toBe(false);
    expect(api.importConversation).not.toHaveBeenCalled();
  });

  it("does not let a finished extract overwrite a newer conversation", async () => {
    const pending = deferred<Graph>();
    const next = deferred<Graph>();
    api.extractConversation.mockImplementation(() => pending.promise);
    api.getGraph.mockImplementation((id: string) => (id === "c2" ? next.promise : Promise.resolve(graph())));
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.extraction_run_id).toBe("run-1"));
    let extraction: Promise<void> = Promise.resolve();
    act(() => {
      extraction = result.current.extractSelected();
    });
    await waitFor(() => expect(result.current.busy).toBe(true));
    act(() => result.current.selectConversation("c2"));
    await waitFor(() => expect(result.current.selectedId).toBe("c2"));
    const stale = { ...graph(), extraction_run_id: "run-old" };
    await act(async () => {
      pending.resolve(stale);
      await extraction;
    });
    expect(result.current.selectedId).toBe("c2");
    expect(result.current.graph?.extraction_run_id).not.toBe("run-old");
    expect(result.current.busy).toBe(true);
    expect(result.current.error).toBeNull();
    await act(async () => {
      next.resolve({ ...graph(), conversation_id: "c2", extraction_run_id: "run-c2" });
    });
    await waitFor(() => expect(result.current.graph?.extraction_run_id).toBe("run-c2"));
    expect(result.current.busy).toBe(false);
  });

  it("keeps the new graph when the follow-up topic refresh fails", async () => {
    api.extractConversation.mockResolvedValue({ ...graph(), extraction_run_id: "run-2" });
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.extraction_run_id).toBe("run-1"));
    api.getTopics.mockRejectedValueOnce(new Error("topics failed"));
    await act(async () => {
      await result.current.extractSelected();
    });
    expect(result.current.graph?.extraction_run_id).toBe("run-2");
    expect(result.current.error).toBe("topics failed");
    expect(result.current.busy).toBe(false);
    expect(result.current.selectedId).toBe("c1");
  });

  it("replaces the graph after a successful re-extraction", async () => {
    const refreshed = { ...graph(), extraction_run_id: "run-2" };
    api.extractConversation.mockResolvedValue(refreshed);
    const { result } = renderHook(() => useWorkspace());
    await waitFor(() => expect(result.current.graph?.extraction_run_id).toBe("run-1"));
    await act(async () => {
      await result.current.extractSelected();
    });
    expect(result.current.graph?.extraction_run_id).toBe("run-2");
    expect(result.current.selectedId).toBe("c1");
    expect(result.current.busy).toBe(false);
    expect(api.importConversation).not.toHaveBeenCalled();
    expect(api.extractConversation).toHaveBeenCalledWith("c1");
  });
});

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
