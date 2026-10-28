import type { Counts } from "../types";

const EMPTY_COUNTS: Counts = { conversations: 0, topics: 0, memories: 0, relationships: 0 };

/** Brand bar and the four dashboard counts. */
export function Header({ counts }: { counts: Counts | null }) {
  const values = counts ?? EMPTY_COUNTS;
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 px-4 py-5 sm:px-6">
      <div>
        <p className="text-xs font-semibold tracking-[0.22em] text-teal uppercase">Conversation memory</p>
        <h1 className="font-serif text-4xl text-ink">RecallFlow</h1>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Count label="Conversations" value={values.conversations} />
        <Count label="Topics" value={values.topics} />
        <Count label="Memories" value={values.memories} />
        <Count label="Relationships" value={values.relationships} />
      </dl>
    </header>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-28 rounded-2xl border border-line bg-white/80 px-3 py-2">
      <dt className="text-[11px] tracking-wide text-stone-500 uppercase">{label}</dt>
      <dd className="font-serif text-2xl text-ink">{value}</dd>
    </div>
  );
}
