"""Rank stored memories. Keyword, graph, and budget modes share this entry point."""

from app.constants import CORRECTION_SOURCE_BONUS, GRAPH_EDGE_BONUS, MAX_GRAPH_CANDIDATES
from app.retrieval.budget import pack
from app.retrieval.expand import expand_memories, seed_memories
from app.retrieval.lexical import lexical_score, query_terms, shared_terms
from app.retrieval.types import RankedMemory, RetrievalCorpus, RetrievalMemory, RetrievalPack


def retrieve(
    corpus: RetrievalCorpus,
    question: str,
    mode: str,
    *,
    limit: int,
    token_budget: int,
) -> RetrievalPack:
    """Return ranked evidence for `question`. This does not generate an answer.

    `limit` is the maximum number of ranked candidates passed to packing.
    Memories past that cut are not backfilled when an earlier candidate is discarded.
    """
    ranked = _rank(corpus, question, mode)[:limit]
    selected, used, discarded = pack(ranked, token_budget, enforce=mode == "budget")
    return RetrievalPack(
        mode=mode,
        evidence=tuple(selected),
        token_budget=token_budget,
        selected_tokens=used,
        discarded=discarded,
    )


def _rank(corpus: RetrievalCorpus, question: str, mode: str) -> list[RankedMemory]:
    terms = query_terms(question)
    seeds = seed_memories(corpus, question)
    seed_ids = {item.id for item in seeds}
    reasons = {item.id: _lexical_reason(terms, item) for item in seeds}
    if mode != "keyword":
        reasons = _merge_expansion(reasons, expand_memories(corpus, seeds))
    by_id = {item.id: item for item in corpus.memories}
    chosen_ids = {item_id for item_id in reasons if item_id in by_id}
    reasons = _annotate_corrections(corpus, reasons, chosen_ids)
    boosted = _correction_sources(corpus, chosen_ids)
    ranked = [
        _scored(by_id[item_id], terms, reasons[item_id], item_id in seed_ids, item_id in boosted)
        for item_id in chosen_ids
    ]
    ranked.sort(key=lambda item: (-item.score, item.memory.id))
    if mode == "keyword":
        return ranked
    return ranked[:MAX_GRAPH_CANDIDATES]


def _merge_expansion(seed_reasons: dict[str, str], expanded: dict[str, str]) -> dict[str, str]:
    """Keep the shared-term reason for seeds and add reasons only for new neighbors."""
    merged = dict(seed_reasons)
    for item_id, reason in expanded.items():
        if item_id not in merged:
            merged[item_id] = reason
    return merged


def _lexical_reason(terms: tuple[str, ...], memory: RetrievalMemory) -> str:
    shared = ", ".join(shared_terms(terms, memory.text)) or "none"
    return f"Shared terms: {shared}."


def _annotate_corrections(corpus: RetrievalCorpus, reasons: dict[str, str], chosen: set[str]) -> dict[str, str]:
    """Name the other endpoint when both sides of a correction are candidates."""
    noted = dict(reasons)
    for edge in corpus.edges:
        if edge.relation_type not in {"SUPERSEDES", "CONTRADICTS"}:
            continue
        if edge.source_id not in chosen or edge.target_id not in chosen:
            continue
        _note(noted, edge.source_id, _source_note(edge.relation_type, edge.target_id))
        _note(noted, edge.target_id, _target_note(edge.relation_type, edge.source_id))
    return noted


def _note(reasons: dict[str, str], item_id: str, text: str) -> None:
    if item_id not in reasons or text in reasons[item_id]:
        return
    reasons[item_id] = f"{reasons[item_id]} {text}"


def _source_note(relation: str, target_id: str) -> str:
    if relation == "SUPERSEDES":
        return f"Supersedes {target_id}."
    return f"Contradicts {target_id}."


def _target_note(relation: str, source_id: str) -> str:
    if relation == "SUPERSEDES":
        return f"Superseded by {source_id}."
    return f"Contradicted by {source_id}."


def _correction_sources(corpus: RetrievalCorpus, chosen: set[str]) -> set[str]:
    sources: set[str] = set()
    for edge in corpus.edges:
        if edge.relation_type not in {"SUPERSEDES", "CONTRADICTS"}:
            continue
        if edge.source_id in chosen and edge.target_id in chosen:
            sources.add(edge.source_id)
    return sources


def _scored(
    memory: RetrievalMemory,
    terms: tuple[str, ...],
    explanation: str,
    is_seed: bool,
    corrects: bool,
) -> RankedMemory:
    score = lexical_score(terms, memory.text)
    if not is_seed:
        score += GRAPH_EDGE_BONUS
    if corrects:
        score += CORRECTION_SOURCE_BONUS
    return RankedMemory(memory=memory, score=round(score, 4), explanation=explanation, selected=True)
