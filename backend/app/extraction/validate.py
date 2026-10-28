"""Check extractor output against the conversation before it is stored."""

from app.constants import PROVIDERS
from app.errors import ExtractionError
from app.extraction.types import (
    ExtractedEntity,
    ExtractedMemory,
    ExtractedRelationship,
    ExtractedTopic,
    ExtractionResult,
    allowed_kind,
    allowed_node,
    allowed_relation,
    memory_endpoint_type,
)


def validate_extraction(result: ExtractionResult, message_ids: set[str]) -> ExtractionResult:
    """Return a cleaned result or raise ExtractionError."""
    if result.provider not in PROVIDERS:
        raise ExtractionError("Extraction provider is not supported.")
    topics = _topics(result.topics)
    memories = _memories(result.memories, topics, message_ids)
    entities = _entities(result.entities, message_ids)
    relationships = _relationships(result.relationships, topics, memories, entities, message_ids)
    return result.model_copy(
        update={"topics": topics, "memories": memories, "entities": entities, "relationships": relationships}
    )


def _topics(topics: list[ExtractedTopic]) -> list[ExtractedTopic]:
    keys = _unique([topic.key for topic in topics], "topic")
    by_key = {topic.key: topic for topic in topics}
    for topic in topics:
        _require_parent(topic, by_key)
    if len(keys) != len(topics):
        raise ExtractionError("Topic keys must be unique.")
    return topics


def _require_parent(topic: ExtractedTopic, by_key: dict[str, ExtractedTopic]) -> None:
    if topic.parent_key is None:
        return
    parent = by_key.get(topic.parent_key)
    if parent is None or parent.parent_key is not None or parent.key == topic.key:
        raise ExtractionError("A subtopic parent is missing or nested too deeply.")


def _memories(
    memories: list[ExtractedMemory],
    topics: list[ExtractedTopic],
    message_ids: set[str],
) -> list[ExtractedMemory]:
    topic_keys = {topic.key for topic in topics}
    seen: set[str] = set()
    for memory in memories:
        _require_fresh(memory.key, seen, "memory")
        if not allowed_kind(memory.kind):
            raise ExtractionError("A memory kind is not supported.")
        if any(key not in topic_keys for key in memory.topic_keys):
            raise ExtractionError("A memory references a missing topic.")
        _require_messages(memory.message_ids, message_ids)
    return memories


def _entities(entities: list[ExtractedEntity], message_ids: set[str]) -> list[ExtractedEntity]:
    seen: set[str] = set()
    for entity in entities:
        _require_fresh(entity.key, seen, "entity")
        _require_messages(entity.message_ids, message_ids)
    return entities


def _relationships(
    relationships: list[ExtractedRelationship],
    topics: list[ExtractedTopic],
    memories: list[ExtractedMemory],
    entities: list[ExtractedEntity],
    message_ids: set[str],
) -> list[ExtractedRelationship]:
    lookup = _endpoint_lookup(topics, memories, entities, message_ids)
    unique: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for relation in relationships:
        _require_relation(relation, lookup, message_ids)
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


def _require_relation(
    relation: ExtractedRelationship,
    lookup: dict[tuple[str, str], str],
    message_ids: set[str],
) -> None:
    if not allowed_relation(relation.relation_type):
        raise ExtractionError("A relationship type is not supported.")
    if not allowed_node(relation.source_type) or not allowed_node(relation.target_type):
        raise ExtractionError("A relationship endpoint type is not supported.")
    if (relation.source_type, relation.source_key) not in lookup:
        raise ExtractionError("A relationship source does not exist in the extraction.")
    if (relation.target_type, relation.target_key) not in lookup:
        raise ExtractionError("A relationship target does not exist in the extraction.")
    _require_messages(relation.evidence_message_ids, message_ids)


def _endpoint_lookup(
    topics: list[ExtractedTopic],
    memories: list[ExtractedMemory],
    entities: list[ExtractedEntity],
    message_ids: set[str],
) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for topic in topics:
        node_type = "subtopic" if topic.parent_key else "topic"
        lookup[(node_type, topic.key)] = topic.key
    for memory in memories:
        lookup[(memory_endpoint_type(memory.kind), memory.key)] = memory.key
    for entity in entities:
        lookup[("entity", entity.key)] = entity.key
    for message_id in message_ids:
        lookup[("message", message_id)] = message_id
    return lookup


def _require_messages(ids: list[str], message_ids: set[str]) -> None:
    if any(item not in message_ids for item in ids):
        raise ExtractionError("Extraction references a message that is not in the conversation.")


def _require_fresh(key: str, seen: set[str], label: str) -> None:
    if key in seen:
        raise ExtractionError(f"Duplicate {label} key in extraction output.")
    seen.add(key)


def _unique(keys: list[str], label: str) -> set[str]:
    if len(keys) != len(set(keys)):
        raise ExtractionError(f"Duplicate {label} key in extraction output.")
    return set(keys)
