/** Search, filters, and extractor notes above the graph. */
export function GraphToolbar({
  search,
  provider,
  limitations,
  topicFilter,
  showingSources,
  onSearch,
  onClearFilter,
  onClearSources,
}: {
  search: string;
  provider: string | null;
  limitations: string[];
  topicFilter: string | null;
  showingSources: boolean;
  onSearch: (value: string) => void;
  onClearFilter: () => void;
  onClearSources: () => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <input
        className="min-w-48 flex-1 rounded-xl border border-line bg-white px-3 py-2 text-sm"
        value={search}
        onChange={(event) => onSearch(event.target.value)}
        placeholder="Search topics, memories, entities"
        aria-label="Search graph"
      />
      {topicFilter ? (
        <button type="button" className="button-secondary" onClick={onClearFilter}>
          All topics
        </button>
      ) : null}
      {showingSources ? (
        <button type="button" className="button-secondary" onClick={onClearSources}>
          Hide messages
        </button>
      ) : null}
      {provider ? <span className="text-xs text-stone-500">Extractor: {provider}</span> : null}
      {limitations.length > 0 ? <Limitations limitations={limitations} /> : null}
    </div>
  );
}

function Limitations({ limitations }: { limitations: string[] }) {
  return (
    <details className="text-xs text-stone-600">
      <summary className="cursor-pointer">Extractor notes</summary>
      <ul className="mt-2 max-w-xl list-disc space-y-1 pl-4">
        {limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </details>
  );
}
