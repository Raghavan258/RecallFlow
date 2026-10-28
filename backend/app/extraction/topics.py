"""Keyword topics and subtopics for the baseline extractor."""

from app.constants import (
    MAX_ROOT_TOPICS,
    MAX_SUBTOPICS_PER_PARENT,
    MIN_TOPIC_DOCUMENT_FREQUENCY,
    SUMMARY_LIMIT,
    TOPIC_JACCARD_LIMIT,
)
from app.extraction.text_utils import phrase_in_text, phrases, title_phrase
from app.extraction.types import ExtractedTopic, MessageInput


def build_topics(messages: list[MessageInput]) -> list[ExtractedTopic]:
    """Select repeated phrases as topics and narrower phrases as subtopics."""
    document_phrases = [phrases(message.content) for message in messages]
    frequency = _document_frequency(document_phrases)
    candidates = _ordered_candidates(frequency)
    roots = _select_roots(candidates, document_phrases)
    subtopics = _select_subtopics(candidates, roots, document_phrases)
    return [_topic(phrase, None) for phrase in roots] + [
        _topic(phrase, parent) for phrase, parent in subtopics
    ]


def matching_topic_keys(text: str, topics: list[ExtractedTopic]) -> list[str]:
    """Return every topic key whose phrase appears in `text`."""
    return [topic.key for topic in topics if any(phrase_in_text(word, text) for word in topic.keywords)]


def root_keys(topic_keys: list[str], topics: list[ExtractedTopic]) -> list[str]:
    """Map topic keys to their root topic keys."""
    by_key = {topic.key: topic for topic in topics}
    roots: list[str] = []
    for key in topic_keys:
        topic = by_key.get(key)
        if topic is None:
            continue
        root = topic.parent_key or topic.key
        if root not in roots:
            roots.append(root)
    return roots


def _document_frequency(document_phrases: list[set[str]]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for found in document_phrases:
        for phrase in found:
            frequency[phrase] = frequency.get(phrase, 0) + 1
    return frequency


def _ordered_candidates(frequency: dict[str, int]) -> list[str]:
    eligible = [phrase for phrase, count in frequency.items() if count >= MIN_TOPIC_DOCUMENT_FREQUENCY]
    return sorted(eligible, key=lambda phrase: (-frequency[phrase], -len(phrase.split()), phrase))


def _select_roots(candidates: list[str], docs: list[set[str]]) -> list[str]:
    roots: list[str] = []
    for phrase in candidates:
        if len(roots) >= MAX_ROOT_TOPICS:
            break
        if _subset_of_any(phrase, roots, docs):
            continue
        if any(_jaccard(phrase, root, docs) >= TOPIC_JACCARD_LIMIT for root in roots):
            continue
        roots.append(phrase)
    return roots


def _select_subtopics(
    candidates: list[str],
    roots: list[str],
    docs: list[set[str]],
) -> list[tuple[str, str]]:
    chosen: list[tuple[str, str]] = []
    counts: dict[str, int] = {root: 0 for root in roots}
    for phrase in candidates:
        parent = _parent_for(phrase, roots, docs)
        if parent is None or counts[parent] >= MAX_SUBTOPICS_PER_PARENT:
            continue
        if _covered_by_sibling(phrase, parent, chosen):
            continue
        chosen.append((phrase, parent))
        counts[parent] += 1
    return chosen


def _subset_of_any(phrase: str, roots: list[str], docs: list[set[str]]) -> bool:
    phrase_docs = _docs_with(phrase, docs)
    return any(phrase_docs < _docs_with(root, docs) for root in roots)


def _parent_for(phrase: str, roots: list[str], docs: list[set[str]]) -> str | None:
    if phrase in roots:
        return None
    parents = _containing_roots(phrase, roots, docs)
    overlapping = [root for root in parents if set(phrase.split()) & set(root.split())]
    pool = overlapping or parents
    if not pool:
        return None
    return min(pool, key=lambda root: (len(_docs_with(root, docs)), root))


def _containing_roots(phrase: str, roots: list[str], docs: list[set[str]]) -> list[str]:
    phrase_docs = _docs_with(phrase, docs)
    return [root for root in roots if phrase_docs < _docs_with(root, docs)]


def _covered_by_sibling(phrase: str, parent: str, chosen: list[tuple[str, str]]) -> bool:
    words = set(phrase.split())
    for existing, existing_parent in chosen:
        if existing_parent == parent and words <= set(existing.split()):
            return True
    return False


def _docs_with(phrase: str, docs: list[set[str]]) -> set[int]:
    return {index for index, found in enumerate(docs) if phrase in found}


def _jaccard(left: str, right: str, docs: list[set[str]]) -> float:
    a = _docs_with(left, docs)
    b = _docs_with(right, docs)
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _topic(phrase: str, parent: str | None) -> ExtractedTopic:
    label = title_phrase(phrase)
    key = f"topic:{phrase.replace(' ', '-')}"
    summary = f"Repeated terms in the conversation: {label}."
    return ExtractedTopic(
        key=key,
        label=label,
        parent_key=None if parent is None else f"topic:{parent.replace(' ', '-')}",
        keywords=[phrase],
        summary=summary[:SUMMARY_LIMIT],
    )
