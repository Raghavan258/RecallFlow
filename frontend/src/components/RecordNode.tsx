import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import type { RecordData } from "../graph/flow";

/** Colored graph card for a topic, memory, entity, decision, or message. */
export function RecordNode({ data }: NodeProps<Node<RecordData>>) {
  return (
    <article className={`record record-${data.kind}`}>
      <Handle type="target" position={Position.Top} className="record-handle" />
      <header className="record-kind">{data.kind}</header>
      <p className="record-label">{data.label}</p>
      {data.expandable ? <ExpandButton data={data} /> : null}
      <button
        type="button"
        className="record-expand"
        onClick={(event) => {
          event.stopPropagation();
          data.onOpen();
        }}
      >
        Inspect
      </button>
      <Handle type="source" position={Position.Bottom} className="record-handle" />
    </article>
  );
}

function ExpandButton({ data }: { data: RecordData }) {
  return (
    <button
      type="button"
      className="record-expand"
      onClick={(event) => {
        event.stopPropagation();
        data.onToggle();
      }}
    >
      {data.expanded ? "Collapse" : "Expand"}
    </button>
  );
}
