"""Greedy token packing. Items that do not fit are discarded, never truncated."""

from app.retrieval.types import RankedMemory


def count_tokens(text: str) -> int:
    """Count whitespace-separated tokens. This is the budget tokenizer."""
    return len(text.split())


def evidence_block(item: RankedMemory) -> str:
    """Return the memory text plus the source identifiers needed to read it."""
    sources = ", ".join(item.memory.source_ids) or ", ".join(item.memory.message_ids)
    return f"{item.memory.text}\nSources: {sources}"


def pack(ranked: list[RankedMemory], budget: int, *, enforce: bool) -> tuple[list[RankedMemory], int, int]:
    """Mark selected rows without exceeding `budget` when `enforce` is true.

    A negative budget is invalid. Zero keeps nothing. A candidate that does not
    fit is discarded whole, and a later smaller candidate can still be kept.
    """
    if budget < 0:
        raise ValueError("Token budget cannot be negative.")
    if not enforce:
        return _mark_all(ranked)
    selected: list[RankedMemory] = []
    used = 0
    discarded = 0
    for item in ranked:
        cost = count_tokens(evidence_block(item))
        if used + cost > budget:
            discarded += 1
            selected.append(_copy(item, selected=False))
            continue
        used += cost
        selected.append(_copy(item, selected=True))
    return selected, used, discarded


def _mark_all(ranked: list[RankedMemory]) -> tuple[list[RankedMemory], int, int]:
    marked = [_copy(item, selected=True) for item in ranked]
    used = sum(count_tokens(evidence_block(item)) for item in marked)
    return marked, used, 0


def _copy(item: RankedMemory, *, selected: bool) -> RankedMemory:
    return RankedMemory(memory=item.memory, score=item.score, explanation=item.explanation, selected=selected)
