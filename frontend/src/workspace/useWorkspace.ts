import { useCallback, useEffect, useRef, useState } from "react";

import {
  extractConversation,
  getGraph,
  getMemory,
  getSample,
  getTopics,
  importConversation,
  listConversations,
} from "../api/client";
import type { ConversationList, Graph, MemoryDetail, Topic } from "../types";
import { buildImport } from "./importing";

/** Dashboard state loaded from the RecallFlow API. */
export function useWorkspace() {
  const catalog = useCatalog();
  const view = useView();
  useGraph(catalog.selectedId, catalog.revision, catalog.setGraph, catalog.setTopics, catalog.setBusy, catalog.setError);
  useMemory(view.selectedNodeId, view.selectedKind, view.setMemory, view.setMemoryError, view.setMemoryLoading);
  const actions = useWorkspaceActions(catalog, view);
  return { ...catalog, ...view, ...actions };
}

function useCatalog() {
  const [list, setList] = useState<ConversationList | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selectedId;
  const [graph, setGraph] = useState<Graph | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    void loadCatalog(setList, setSelectedId, setError);
  }, []);
  return {
    list, setList, selectedId, setSelectedId, selectedRef, graph, setGraph, topics, setTopics, error, setError, notice, setNotice,
    busy, setBusy, revision, setRevision,
  };
}

function useView() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [topicFilter, setTopicFilter] = useState<string | null>(null);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [memory, setMemory] = useState<MemoryDetail | null>(null);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [selectedKind, setSelectedKind] = useState<string | null>(null);
  const clear = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedKind(null);
    setExpanded([]);
    setSearch("");
    setTopicFilter(null);
    setSourceIds([]);
    setMemory(null);
  }, []);
  return {
    selectedNodeId, setSelectedNodeId, expanded, setExpanded, search, setSearch, topicFilter, setTopicFilter,
    sourceIds, setSourceIds, memory, setMemory, memoryError, setMemoryError, memoryLoading, setMemoryLoading,
    selectedKind, setSelectedKind, clear,
  };
}

function useGraph(
  selectedId: string | null,
  revision: number,
  setGraph: (value: Graph | null) => void,
  setTopics: (value: Topic[]) => void,
  setBusy: (value: boolean) => void,
  setError: (value: string | null) => void,
) {
  const generation = useRef(0);
  const shownConversation = useRef<string | null>(null);
  useEffect(() => {
    const requestId = ++generation.current;
    const activeId = selectedId;
    if (!startGraphLoad(activeId, shownConversation, setGraph, setTopics, setBusy, setError)) {
      return;
    }
    void Promise.all([getGraph(activeId), getTopics(activeId)])
      .then(([graph, topics]) => publishGraph(requestId, generation, graph, topics, setGraph, setTopics, setBusy))
      .catch((caught: unknown) => failGraph(requestId, generation, caught, setError, setBusy));
  }, [selectedId, revision, setGraph, setTopics, setBusy, setError]);
}

function useMemory(
  nodeId: string | null,
  kind: string | null,
  setMemory: (value: MemoryDetail | null) => void,
  setMemoryError: (value: string | null) => void,
  setMemoryLoading: (value: boolean) => void,
) {
  const generation = useRef(0);
  useEffect(() => {
    const requestId = ++generation.current;
    if (!startMemoryLoad(nodeId, kind, setMemory, setMemoryError, setMemoryLoading)) {
      return;
    }
    void getMemory(nodeId)
      .then((detail) => publishMemory(requestId, generation, nodeId, detail, setMemory, setMemoryError, setMemoryLoading))
      .catch((caught: unknown) => failMemory(requestId, generation, caught, setMemory, setMemoryError, setMemoryLoading));
  }, [nodeId, kind, setMemory, setMemoryError, setMemoryLoading]);
}

function useWorkspaceActions(catalog: ReturnType<typeof useCatalog>, view: ReturnType<typeof useView>) {
  const extractLock = useRef(false);
  const importText = useCallback((mode: "paste" | "json", title: string, text: string) => {
    return store(buildImport(mode, title, text), catalog, view.clear);
  }, [catalog, view.clear]);
  const loadSample = useCallback(() => store(getSample(), catalog, view.clear), [catalog, view.clear]);
  const extractSelected = useCallback(
    () => extractCurrent(catalog, view.clear, extractLock),
    [catalog, view.clear],
  );
  const focusTopic = useCallback((id: string) => {
    const topic = catalog.topics.find((item) => item.id === id);
    view.setTopicFilter(id);
    view.setSelectedNodeId(id);
    view.setSelectedKind(topic?.parent_id ? "subtopic" : "topic");
    view.setExpanded((current) => unique([...current, id, topic?.parent_id].filter((item): item is string => Boolean(item))));
  }, [catalog.topics, view]);
  return {
    importText,
    loadSample,
    extractSelected,
    focusTopic,
    toggleExpanded: (id: string) => view.setExpanded((current) => toggle(current, id)),
    clearFilter: () => view.setTopicFilter(null),
    showSources: (ids: string[]) => view.setSourceIds(ids),
    clearSources: () => view.setSourceIds([]),
    selectNode: (id: string) => selectNode(id, catalog.graph, view.setSelectedNodeId, view.setSelectedKind),
    setSearch: view.setSearch,
    selectConversation: (id: string) => {
      catalog.setSelectedId(id || null);
      view.clear();
    },
  };
}

async function loadCatalog(
  setList: (value: ConversationList) => void,
  setSelectedId: (value: (current: string | null) => string | null) => void,
  setError: (value: string) => void,
) {
  try {
    const data = await listConversations();
    setList(data);
    if (data.items[0]) {
      setSelectedId((current) => current ?? data.items[0].id);
    }
  } catch (caught) {
    setError(message(caught));
  }
}

function startGraphLoad(
  selectedId: string | null,
  shownConversation: { current: string | null },
  setGraph: (value: Graph | null) => void,
  setTopics: (value: Topic[]) => void,
  setBusy: (value: boolean) => void,
  setError: (value: string | null) => void,
): selectedId is string {
  if (!selectedId) {
    shownConversation.current = null;
    setGraph(null);
    setTopics([]);
    setBusy(false);
    return false;
  }
  if (shownConversation.current !== selectedId) {
    setGraph(null);
    setTopics([]);
    shownConversation.current = selectedId;
  }
  setBusy(true);
  setError(null);
  return true;
}

function publishGraph(
  requestId: number,
  generation: { current: number },
  graph: Graph,
  topics: Topic[],
  setGraph: (value: Graph) => void,
  setTopics: (value: Topic[]) => void,
  setBusy: (value: boolean) => void,
) {
  if (generation.current !== requestId) {
    return;
  }
  setGraph(graph);
  setTopics(topics);
  setBusy(false);
}

function failGraph(
  requestId: number,
  generation: { current: number },
  caught: unknown,
  setError: (value: string | null) => void,
  setBusy: (value: boolean) => void,
) {
  if (generation.current !== requestId) {
    return;
  }
  setError(message(caught));
  setBusy(false);
}

function startMemoryLoad(
  nodeId: string | null,
  kind: string | null,
  setMemory: (value: MemoryDetail | null) => void,
  setMemoryError: (value: string | null) => void,
  setMemoryLoading: (value: boolean) => void,
): nodeId is string {
  if (!nodeId || (kind !== "memory" && kind !== "decision")) {
    setMemory(null);
    setMemoryError(null);
    setMemoryLoading(false);
    return false;
  }
  setMemory(null);
  setMemoryError(null);
  setMemoryLoading(true);
  return true;
}

function publishMemory(
  requestId: number,
  generation: { current: number },
  nodeId: string,
  detail: MemoryDetail,
  setMemory: (value: MemoryDetail | null) => void,
  setMemoryError: (value: string | null) => void,
  setMemoryLoading: (value: boolean) => void,
) {
  if (generation.current !== requestId || detail.id !== nodeId) {
    return;
  }
  setMemory(detail);
  setMemoryError(null);
  setMemoryLoading(false);
}

function failMemory(
  requestId: number,
  generation: { current: number },
  caught: unknown,
  setMemory: (value: MemoryDetail | null) => void,
  setMemoryError: (value: string | null) => void,
  setMemoryLoading: (value: boolean) => void,
) {
  if (generation.current !== requestId) {
    return;
  }
  setMemory(null);
  setMemoryError(message(caught));
  setMemoryLoading(false);
}

async function store(
  payload: Promise<import("../types").ImportRequest> | import("../types").ImportRequest,
  catalog: ReturnType<typeof useCatalog>,
  clear: () => void,
) {
  catalog.setBusy(true);
  catalog.setError(null);
  catalog.setNotice(null);
  try {
    const created = await importConversation(await payload);
    clear();
    catalog.setSelectedId(created.id);
    await extractConversation(created.id);
    catalog.setList(await listConversations());
    catalog.setRevision((current) => current + 1);
  } catch (caught) {
    catalog.setError(message(caught));
  } finally {
    catalog.setBusy(false);
  }
}

async function extractCurrent(
  catalog: ReturnType<typeof useCatalog>,
  clear: () => void,
  lock: { current: boolean },
) {
  if (!catalog.selectedId || catalog.busy || lock.current) {
    return;
  }
  const conversationId = catalog.selectedId;
  lock.current = true;
  catalog.setBusy(true);
  catalog.setError(null);
  catalog.setNotice(null);
  try {
    await runExtract(conversationId, catalog, clear);
  } catch (caught) {
    if (catalog.selectedRef.current === conversationId) {
      catalog.setError(message(caught));
    }
  } finally {
    lock.current = false;
    if (catalog.selectedRef.current === conversationId) {
      catalog.setBusy(false);
    }
  }
}

async function runExtract(conversationId: string, catalog: ReturnType<typeof useCatalog>, clear: () => void) {
  const graph = await extractConversation(conversationId);
  if (catalog.selectedRef.current === conversationId) {
    catalog.setGraph(graph);
  }
  const [topics, list] = await Promise.all([getTopics(conversationId), listConversations()]);
  catalog.setList(list);
  if (catalog.selectedRef.current !== conversationId) {
    return;
  }
  catalog.setTopics(topics);
  clear();
  catalog.setNotice("Extraction finished. The graph shows the latest run.");
}

function selectNode(
  id: string,
  graph: Graph | null,
  setSelectedNodeId: (value: string) => void,
  setSelectedKind: (value: string | null) => void,
) {
  setSelectedNodeId(id);
  setSelectedKind(graph?.nodes.find((node) => node.id === id)?.type ?? null);
}

function toggle(current: string[], id: string): string[] {
  return current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function message(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Unexpected error.";
}
