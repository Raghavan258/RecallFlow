import type { Topic } from "../types";

/** Detected topics for the open conversation. */
export function TopicSidebar({
  topics,
  activeId,
  expanded,
  onFocus,
}: {
  topics: Topic[];
  activeId: string | null;
  expanded: readonly string[];
  onFocus: (id: string) => void;
}) {
  const roots = topics.filter((topic) => topic.parent_id === null);
  return (
    <section className="panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="panel-title">Topics</h2>
        <span className="text-xs text-stone-500">{topics.length}</span>
      </div>
      {roots.length === 0 ? <p className="text-sm text-stone-600">Topics appear here after extraction.</p> : null}
      <ul className="space-y-2">
        {roots.map((topic) => (
          <TopicBranch key={topic.id} topic={topic} topics={topics} activeId={activeId} expanded={expanded} onFocus={onFocus} />
        ))}
      </ul>
    </section>
  );
}

function TopicBranch({
  topic,
  topics,
  activeId,
  expanded,
  onFocus,
}: {
  topic: Topic;
  topics: Topic[];
  activeId: string | null;
  expanded: readonly string[];
  onFocus: (id: string) => void;
}) {
  const children = topics.filter((item) => item.parent_id === topic.id);
  return (
    <li>
      <TopicButton topic={topic} active={activeId === topic.id} expanded={expanded.includes(topic.id)} onFocus={onFocus} />
      {children.length > 0 ? (
        <ul className="mt-1 ml-3 space-y-1 border-l border-line pl-3">
          {children.map((child) => (
            <li key={child.id}>
              <TopicButton topic={child} active={activeId === child.id} expanded={expanded.includes(child.id)} onFocus={onFocus} />
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function TopicButton({
  topic,
  active,
  expanded,
  onFocus,
}: {
  topic: Topic;
  active: boolean;
  expanded: boolean;
  onFocus: (id: string) => void;
}) {
  return (
    <button type="button" className={active ? "topic-button topic-button-active" : "topic-button"} onClick={() => onFocus(topic.id)}>
      <span>{topic.label}</span>
      <span className="text-xs text-stone-500">{expanded ? "open" : topic.memory_count}</span>
    </button>
  );
}
