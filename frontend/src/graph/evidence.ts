/**
 * Evidence that belongs to the node currently selected.
 * A failed or in-flight request must not keep showing another memory.
 */
export function evidenceForSelection<T extends { id: string }>(memory: T | null, selectedId: string | null): T | null {
  if (!memory || memory.id !== selectedId) {
    return null;
  }
  return memory;
}
