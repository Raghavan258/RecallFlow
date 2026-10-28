"""Pure graph projection. Persistence and providers stay outside this module."""

from dataclasses import dataclass
from datetime import datetime

from app.constants import LABEL_LIMIT
from app.extraction.text_utils import name_in_text
from app.extraction.types import memory_endpoint_type
from app.schemas import GraphEdgeOut, GraphNodeOut
from app.services.clock import utc_iso


@dataclass(frozen=True)
class TopicView:
    """Topic row needed to draw a node."""

    id: str
    label: str
    parent_id: str | None
    keywords: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class MemoryView:
    """Memory row needed to draw a node."""

    id: str
    kind: str
    text: str
    topic_ids: tuple[str, ...]
    message_ids: tuple[str, ...]
    confidence: float | None


@dataclass(frozen=True)
class EntityView:
    """Entity row needed to draw a node."""

    id: str
    name: str
    entity_type: str
    message_ids: tuple[str, ...]


@dataclass(frozen=True)
class MessageView:
    """Original message that can be revealed as evidence."""

    id: str
    speaker: str
    content: str
    position: int
    source_id: str | None
    timestamp: datetime | None


@dataclass(frozen=True)
class RelationView:
    """Stored relationship projected as an edge."""

    id: str
    relation_type: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    evidence_message_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphRecords:
    """Inputs for one extraction run."""

    topics: tuple[TopicView, ...]
    memories: tuple[MemoryView, ...]
    entities: tuple[EntityView, ...]
    messages: tuple[MessageView, ...]
    relationships: tuple[RelationView, ...]


def build_graph(records: GraphRecords) -> tuple[list[GraphNodeOut], list[GraphEdgeOut]]:
    """Project stored records into nodes and edges without adding links."""
    nodes = [
        *_topic_nodes(records.topics),
        *_memory_nodes(records.memories),
        *_entity_nodes(records.entities, records.memories),
        *_message_nodes(records.messages),
    ]
    edges = [_edge(item) for item in records.relationships]
    return nodes, edges


def _topic_nodes(topics: tuple[TopicView, ...]) -> list[GraphNodeOut]:
    return [_topic_node(topic) for topic in topics]


def _topic_node(topic: TopicView) -> GraphNodeOut:
    node_type = "subtopic" if topic.parent_id else "topic"
    topic_ids = [topic.parent_id] if topic.parent_id else [topic.id]
    return GraphNodeOut(
        id=topic.id,
        type=node_type,
        label=topic.label,
        initially_visible=node_type == "topic",
        topic_ids=topic_ids,
        payload={"keywords": list(topic.keywords), "summary": topic.summary, "parent_id": topic.parent_id},
    )


def _memory_nodes(memories: tuple[MemoryView, ...]) -> list[GraphNodeOut]:
    return [
        GraphNodeOut(
            id=memory.id,
            type=memory_endpoint_type(memory.kind),
            label=_short(memory.text),
            initially_visible=False,
            topic_ids=list(memory.topic_ids),
            payload={
                "kind": memory.kind,
                "text": memory.text,
                "confidence": memory.confidence,
                "message_ids": list(memory.message_ids),
            },
        )
        for memory in memories
    ]


def _entity_nodes(entities: tuple[EntityView, ...], memories: tuple[MemoryView, ...]) -> list[GraphNodeOut]:
    return [_entity_node(entity, memories) for entity in entities]


def _entity_node(entity: EntityView, memories: tuple[MemoryView, ...]) -> GraphNodeOut:
    return GraphNodeOut(
        id=entity.id,
        type="entity",
        label=entity.name,
        initially_visible=False,
        topic_ids=_entity_topics(entity, memories),
        payload={"entity_type": entity.entity_type, "message_ids": list(entity.message_ids)},
    )


def _entity_topics(entity: EntityView, memories: tuple[MemoryView, ...]) -> list[str]:
    topic_ids: list[str] = []
    for memory in memories:
        if not name_in_text(entity.name, memory.text):
            continue
        if not set(entity.message_ids) & set(memory.message_ids):
            continue
        for topic_id in memory.topic_ids:
            if topic_id not in topic_ids:
                topic_ids.append(topic_id)
    return topic_ids


def _message_nodes(messages: tuple[MessageView, ...]) -> list[GraphNodeOut]:
    return [
        GraphNodeOut(
            id=message.id,
            type="message",
            label=_short(f"{message.speaker}: {message.content}"),
            initially_visible=False,
            topic_ids=[],
            payload={
                "speaker": message.speaker,
                "content": message.content,
                "position": message.position,
                "source_id": message.source_id,
                "timestamp": _timestamp(message.timestamp),
            },
        )
        for message in messages
    ]


def _edge(relation: RelationView) -> GraphEdgeOut:
    return GraphEdgeOut(
        id=relation.id,
        type=relation.relation_type,
        source=relation.source_id,
        target=relation.target_id,
        source_type=relation.source_type,
        target_type=relation.target_type,
        evidence_message_ids=list(relation.evidence_message_ids),
    )


def _timestamp(value: datetime | None) -> str | None:
    return utc_iso(value)


def _short(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= LABEL_LIMIT:
        return compact
    return compact[: LABEL_LIMIT - 1].rstrip() + "…"
