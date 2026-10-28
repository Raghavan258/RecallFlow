import { DetailsPanel } from "../components/DetailsPanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { GraphCanvas } from "../components/GraphCanvas";
import { GraphToolbar } from "../components/GraphToolbar";
import { Header } from "../components/Header";
import { ImportPanel } from "../components/ImportPanel";
import { RetrievalPanel } from "../components/RetrievalPanel";
import { TopicSidebar } from "../components/TopicSidebar";
import { acceptedTopicIds } from "../graph/visibility";
import { useRetrieval } from "../workspace/useRetrieval";
import { useWorkspace } from "../workspace/useWorkspace";

/** RecallFlow workspace: import, topic list, graph, and evidence. */
export function Dashboard() {
  const workspace = useWorkspace();
  const retrieval = useRetrieval(workspace.selectedId);
  const selected = workspace.graph?.nodes.find((node) => node.id === workspace.selectedNodeId) ?? null;
  const topicIds = acceptedTopicIds(workspace.topics, workspace.topicFilter);
  return (
    <div className="min-h-screen">
      <Header counts={workspace.list?.totals ?? null} />
      {workspace.error ? <p className="mx-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-800 sm:mx-6">{workspace.error}</p> : null}
      {workspace.notice ? <p className="mx-4 rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-900 sm:mx-6">{workspace.notice}</p> : null}
      <main className="grid gap-4 px-4 pb-8 sm:px-6 lg:grid-cols-[300px_minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <ImportPanel
            conversations={workspace.list?.items ?? []}
            selectedId={workspace.selectedId}
            busy={workspace.busy}
            onSelect={workspace.selectConversation}
            onImport={workspace.importText}
            onSample={() => void workspace.loadSample()}
            onExtract={() => void workspace.extractSelected()}
          />
          <TopicSidebar topics={workspace.topics} activeId={workspace.topicFilter} expanded={workspace.expanded} onFocus={workspace.focusTopic} />
        </div>
        <section className="panel flex min-h-[70vh] flex-col">
          <GraphToolbar
            search={workspace.search}
            provider={workspace.graph?.provider ?? null}
            limitations={workspace.graph?.limitations ?? []}
            topicFilter={workspace.topicFilter}
            showingSources={workspace.sourceIds.length > 0}
            onSearch={workspace.setSearch}
            onClearFilter={workspace.clearFilter}
            onClearSources={workspace.clearSources}
          />
          <GraphCanvas
            graph={workspace.graph}
            search={workspace.search}
            topicIds={topicIds}
            expanded={workspace.expanded}
            sourceMessageIds={workspace.sourceIds}
            conversationSelected={Boolean(workspace.selectedId)}
            selectedId={workspace.selectedNodeId}
            busy={workspace.busy}
            onSelect={workspace.selectNode}
            onToggle={workspace.toggleExpanded}
          />
        </section>
        <div className="space-y-4">
          <RetrievalPanel
            disabled={!workspace.selectedId}
            loading={retrieval.loading}
            error={retrieval.error}
            result={retrieval.result}
            onAsk={retrieval.ask}
            onShowSources={workspace.showSources}
          />
          <DetailsPanel graph={workspace.graph} node={selected} topics={workspace.topics} />
          <EvidencePanel
            node={selected}
            memory={workspace.memory}
            loading={workspace.memoryLoading}
            error={workspace.memoryError}
            onShowSources={workspace.showSources}
          />
        </div>
      </main>
    </div>
  );
}
