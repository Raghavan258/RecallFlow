"""Evidence-backed relationships for the baseline extractor."""

import re

from app.constants import MIN_SHARED_CORRECTION_TOKENS
from app.extraction.text_utils import name_in_text, phrase_in_text, shared_tokens
from app.extraction.topics import root_keys
from app.extraction.types import (
    ExtractedEntity,
    ExtractedMemory,
    ExtractedRelationship,
    ExtractedTopic,
    memory_endpoint_type,
)

DEPENDS_PATTERN = re.compile(r"^(?P<source>.+?)\bdepends on\b(?P<target>.+)$", re.IGNORECASE)
CONTRADICTION_PATTERN = re.compile(r"\b(actually|no longer|contradicts?)\b", re.IGNORECASE)
SUPERSEDE_PATTERN = re.compile(r"\bsupersedes?\b", re.IGNORECASE)


def build_relationships(
    topics: list[ExtractedTopic],
    memories: list[ExtractedMemory],
    entities: list[ExtractedEntity],
) -> list[ExtractedRelationship]:
    """Create relationships that each have a source cue or a shared record."""
    relations = [
        *_contains_topics(topics),
        *_contains_memories(memories, topics),
        *_derived_from(memories),
        *_mentions(memories, entities),
        *_related_topics(memories, topics),
        *_supports(memories),
        *_depends_on(memories, topics),
        *_corrections(memories),
    ]
    return _dedupe(relations)


def _contains_topics(topics: list[ExtractedTopic]) -> list[ExtractedRelationship]:
    return [
        _edge("CONTAINS", "topic", topic.parent_key or "", "subtopic", topic.key, [])
        for topic in topics
        if topic.parent_key
    ]


def _contains_memories(
    memories: list[ExtractedMemory],
    topics: list[ExtractedTopic],
) -> list[ExtractedRelationship]:
    kinds = {topic.key: ("subtopic" if topic.parent_key else "topic") for topic in topics}
    edges: list[ExtractedRelationship] = []
    for memory in memories:
        target_type = memory_endpoint_type(memory.kind)
        edges.extend(
            _edge("CONTAINS", kinds[key], key, target_type, memory.key, memory.message_ids)
            for key in memory.topic_keys
            if key in kinds
        )
    return edges


def _derived_from(memories: list[ExtractedMemory]) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    for memory in memories:
        source_type = memory_endpoint_type(memory.kind)
        edges.extend(
            _edge("DERIVED_FROM", source_type, memory.key, "message", message_id, [message_id])
            for message_id in memory.message_ids
        )
    return edges


def _mentions(
    memories: list[ExtractedMemory],
    entities: list[ExtractedEntity],
) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    for memory in memories:
        edges.extend(_memory_mentions(memory, entities))
    return edges


def _memory_mentions(
    memory: ExtractedMemory,
    entities: list[ExtractedEntity],
) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    source_type = memory_endpoint_type(memory.kind)
    for entity in entities:
        evidence = [item for item in memory.message_ids if item in entity.message_ids]
        if evidence and name_in_text(entity.name, memory.text):
            edges.append(_edge("MENTIONS", source_type, memory.key, "entity", entity.key, evidence))
    return edges


def _related_topics(
    memories: list[ExtractedMemory],
    topics: list[ExtractedTopic],
) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    seen: set[tuple[str, str]] = set()
    for memory in memories:
        pair = _root_pair(memory, topics)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        edges.append(_edge("RELATED_TO", "topic", pair[0], "topic", pair[1], memory.message_ids))
    return edges


def _root_pair(memory: ExtractedMemory, topics: list[ExtractedTopic]) -> tuple[str, str] | None:
    roots = sorted(root_keys(memory.topic_keys, topics))
    if len(roots) != 2:
        return None
    return roots[0], roots[1]


def _supports(memories: list[ExtractedMemory]) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    for group in _groups(memories).values():
        if _has_correction_cue(group):
            continue
        edges.extend(_support_group(group))
    return edges


def _has_correction_cue(group: list[ExtractedMemory]) -> bool:
    return any(
        CONTRADICTION_PATTERN.search(item.text) or SUPERSEDE_PATTERN.search(item.text) for item in group
    )


def _support_group(group: list[ExtractedMemory]) -> list[ExtractedRelationship]:
    decisions = [item for item in group if item.kind == "decision"]
    others = [item for item in group if item.kind != "decision"]
    return [
        _edge("SUPPORTS", memory_endpoint_type(other.kind), other.key, "decision", decision.key, other.message_ids)
        for other in others
        for decision in decisions
        if set(other.topic_keys) & set(decision.topic_keys)
    ]


def _depends_on(
    memories: list[ExtractedMemory],
    topics: list[ExtractedTopic],
) -> list[ExtractedRelationship]:
    by_key = {topic.key: topic for topic in topics}
    edges: list[ExtractedRelationship] = []
    for memory in memories:
        edge = _depends_edge(memory, by_key)
        if edge is not None:
            edges.append(edge)
    return edges


def _depends_edge(
    memory: ExtractedMemory,
    by_key: dict[str, ExtractedTopic],
) -> ExtractedRelationship | None:
    match = DEPENDS_PATTERN.match(memory.text.rstrip(".!?"))
    if match is None:
        return None
    source = _longest_topic(match.group("source"), memory.topic_keys, by_key)
    target = _longest_topic(match.group("target"), memory.topic_keys, by_key)
    if source is None or target is None or source.key == target.key:
        return None
    return _edge(
        "DEPENDS_ON",
        "subtopic" if source.parent_key else "topic",
        source.key,
        "subtopic" if target.parent_key else "topic",
        target.key,
        memory.message_ids,
    )


def _longest_topic(
    fragment: str,
    topic_keys: list[str],
    by_key: dict[str, ExtractedTopic],
) -> ExtractedTopic | None:
    matches = [
        by_key[key]
        for key in topic_keys
        if key in by_key and any(phrase_in_text(word, fragment) for word in by_key[key].keywords)
    ]
    if not matches:
        return None
    return max(matches, key=lambda topic: (len(topic.keywords[0].split()), topic.key))


def _corrections(memories: list[ExtractedMemory]) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    for index, memory in enumerate(memories):
        edges.extend(_correction_edges(memories[:index], memory))
    return edges


def _correction_edges(
    earlier: list[ExtractedMemory],
    memory: ExtractedMemory,
) -> list[ExtractedRelationship]:
    edges: list[ExtractedRelationship] = []
    if CONTRADICTION_PATTERN.search(memory.text):
        _append_correction(edges, "CONTRADICTS", earlier, memory)
    if SUPERSEDE_PATTERN.search(memory.text):
        _append_correction(edges, "SUPERSEDES", earlier, memory)
    return edges


def _append_correction(
    edges: list[ExtractedRelationship],
    relation_type: str,
    earlier: list[ExtractedMemory],
    memory: ExtractedMemory,
) -> None:
    target = _correction_target(earlier, memory)
    if target is not None:
        edges.append(_link_memories(relation_type, memory, target, _correction_evidence(memory, target)))


def _correction_target(
    earlier: list[ExtractedMemory],
    memory: ExtractedMemory,
) -> ExtractedMemory | None:
    best: ExtractedMemory | None = None
    best_score = MIN_SHARED_CORRECTION_TOKENS - 1
    for candidate in earlier:
        score = len(shared_tokens(memory.text, candidate.text))
        if score >= MIN_SHARED_CORRECTION_TOKENS and score >= best_score:
            best = candidate
            best_score = score
    return best


def _link_memories(
    relation_type: str,
    source: ExtractedMemory,
    target: ExtractedMemory,
    evidence: list[str] | None = None,
) -> ExtractedRelationship:
    return _edge(
        relation_type,
        memory_endpoint_type(source.kind),
        source.key,
        memory_endpoint_type(target.kind),
        target.key,
        evidence if evidence is not None else source.message_ids,
    )


def _correction_evidence(source: ExtractedMemory, target: ExtractedMemory) -> list[str]:
    evidence = list(source.message_ids)
    for message_id in target.message_ids:
        if message_id not in evidence:
            evidence.append(message_id)
    return evidence


def _groups(memories: list[ExtractedMemory]) -> dict[str, list[ExtractedMemory]]:
    grouped: dict[str, list[ExtractedMemory]] = {}
    for memory in memories:
        for message_id in memory.message_ids:
            grouped.setdefault(message_id, []).append(memory)
    return grouped


def _edge(
    relation_type: str,
    source_type: str,
    source_key: str,
    target_type: str,
    target_key: str,
    evidence: list[str],
) -> ExtractedRelationship:
    return ExtractedRelationship(
        relation_type=relation_type,
        source_type=source_type,
        source_key=source_key,
        target_type=target_type,
        target_key=target_key,
        evidence_message_ids=evidence,
    )


def _dedupe(relations: list[ExtractedRelationship]) -> list[ExtractedRelationship]:
    unique: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for relation in relations:
        key = (
            relation.relation_type,
            relation.source_type,
            relation.source_key,
            relation.target_type,
            relation.target_key,
        )
        if key not in seen:
            seen.add(key)
            unique.append(relation)
    return unique
