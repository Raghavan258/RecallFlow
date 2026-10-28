"""One-hop expansion from lexical seeds along stored relationships."""

from app.constants import STRONG_MEMORY_RELATIONS
from app.extraction.relations import DEPENDS_PATTERN
from app.extraction.text_utils import tokens
from app.retrieval.lexical import lexical_score, query_terms
from app.retrieval.types import RetrievalCorpus, RetrievalMemory

MEMORY_RELATIONS = set(STRONG_MEMORY_RELATIONS)
MIN_DEPENDS_TERMS = 2


def seed_memories(corpus: RetrievalCorpus, question: str) -> list[RetrievalMemory]:
    """Return memories that share at least one question term."""
    terms = query_terms(question)
    return [item for item in corpus.memories if lexical_score(terms, item.text) > 0]


def expand_memories(corpus: RetrievalCorpus, seeds: list[RetrievalMemory]) -> dict[str, str]:
    """Return memory id to explanation for seeds plus neighbors of those seeds only."""
    chosen: dict[str, str] = {item.id: _seed_reason(item) for item in seeds}
    _add_memory_edges(corpus, seeds, chosen)
    _add_depends_neighbors(corpus, seeds, chosen)
    _add_stated_depends(corpus, seeds, chosen)
    return chosen


def _seed_reason(memory: RetrievalMemory) -> str:
    return f"Shared wording with the question in: {memory.text}"


def _add_memory_edges(
    corpus: RetrievalCorpus,
    seeds: list[RetrievalMemory],
    chosen: dict[str, str],
) -> None:
    seed_ids = {item.id for item in seeds}
    for edge in corpus.edges:
        if edge.relation_type not in MEMORY_RELATIONS:
            continue
        _link_from_seed(chosen, seed_ids, edge.source_id, edge.target_id, edge.relation_type)
        _link_from_seed(chosen, seed_ids, edge.target_id, edge.source_id, edge.relation_type)


def _link_from_seed(
    chosen: dict[str, str],
    seed_ids: set[str],
    known: str,
    other: str,
    relation: str,
) -> None:
    if known in seed_ids and other not in chosen:
        chosen[other] = f"Included through a stored {relation} link."


def _add_depends_neighbors(
    corpus: RetrievalCorpus,
    seeds: list[RetrievalMemory],
    chosen: dict[str, str],
) -> None:
    seed_topics = {topic_id for item in seeds for topic_id in item.topic_ids}
    related = _depends_topics(corpus, seed_topics)
    for memory in corpus.memories:
        if memory.id in chosen or not set(memory.topic_ids) & related:
            continue
        chosen[memory.id] = "Included through a stored DEPENDS_ON topic link."


def _add_stated_depends(corpus: RetrievalCorpus, seeds: list[RetrievalMemory], chosen: dict[str, str]) -> None:
    """Follow an explicit 'depends on' phrase when the extractor stored no edge."""
    phrases = _target_phrases(seeds)
    for memory in corpus.memories:
        if memory.id in chosen:
            continue
        matched = _matched_phrase(memory.text, phrases)
        if matched is None:
            continue
        chosen[memory.id] = f"Included because a retrieved memory depends on: {', '.join(matched)}."


def _target_phrases(seeds: list[RetrievalMemory]) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    for seed in seeds:
        match = DEPENDS_PATTERN.match(seed.text.rstrip(".!?"))
        if match is None:
            continue
        words = tuple(dict.fromkeys(tokens(match.group("target"))))
        if len(words) >= MIN_DEPENDS_TERMS:
            found.append(words)
    return found


def _matched_phrase(text: str, phrases: list[tuple[str, ...]]) -> tuple[str, ...] | None:
    present = set(tokens(text))
    for phrase in phrases:
        if all(word in present for word in phrase):
            return phrase
    return None


def _depends_topics(corpus: RetrievalCorpus, seed_topics: set[str]) -> set[str]:
    """Follow DEPENDS_ON from the depending topic toward the topic it needs."""
    found: set[str] = set()
    for edge in corpus.edges:
        if edge.relation_type != "DEPENDS_ON":
            continue
        if edge.source_id in seed_topics:
            found.add(edge.target_id)
    return found
