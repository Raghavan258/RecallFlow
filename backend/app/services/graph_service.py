"""Read stored records and project the conversation graph."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.graph.builder import (
    EntityView,
    GraphRecords,
    MemoryView,
    MessageView,
    RelationView,
    TopicView,
    build_graph,
)
from app.models import (
    Conversation,
    Entity,
    EntitySource,
    ExtractionRun,
    GraphRelationship,
    Memory,
    MemorySource,
    MemoryTopic,
    Message,
    Topic,
)
from app.schemas import GraphOut, MemoryDetail, MessageOut, RelationshipOut, TopicBrief, TopicOut
from app.services.clock import ensure_utc
from app.services.conversations import latest_run, list_messages


def get_graph(session: Session, conversation_id: str) -> GraphOut:
    """Return the latest graph, or an empty graph when extraction has not run."""
    _require_conversation(session, conversation_id)
    run = latest_run(session, conversation_id)
    if run is None:
        return _empty_graph(conversation_id)
    nodes, edges = build_graph(_records(session, conversation_id, run.id))
    return GraphOut(
        conversation_id=conversation_id,
        extraction_run_id=run.id,
        provider=run.provider,
        limitations=list(run.limitations),
        nodes=nodes,
        edges=edges,
    )


def list_topics(session: Session, conversation_id: str | None) -> list[TopicOut]:
    """Return topics for one conversation or for every latest extraction."""
    topics: list[TopicOut] = []
    for run in _runs(session, conversation_id):
        rows = session.scalars(select(Topic).where(Topic.extraction_run_id == run.id).order_by(Topic.label)).all()
        topics.extend(_topic_out(session, row) for row in rows)
    return topics


def get_memory(session: Session, memory_id: str) -> MemoryDetail:
    """Return a memory with its topics, relationships, and source messages."""
    memory = session.get(Memory, memory_id)
    if memory is None:
        raise AppError(404, "Memory not found.")
    run = session.get(ExtractionRun, memory.extraction_run_id)
    if run is None:
        raise AppError(404, "Extraction run not found.")
    return _memory_detail(session, memory, run)


def _records(session: Session, conversation_id: str, run_id: str) -> GraphRecords:
    return GraphRecords(
        topics=_topic_views(session, run_id),
        memories=_memory_views(session, run_id),
        entities=_entity_views(session, run_id),
        messages=_message_views(session, conversation_id),
        relationships=_relation_views(session, run_id),
    )


def _topic_views(session: Session, run_id: str) -> tuple[TopicView, ...]:
    rows = session.scalars(select(Topic).where(Topic.extraction_run_id == run_id).order_by(Topic.label)).all()
    return tuple(
        TopicView(
            id=row.id,
            label=row.label,
            parent_id=row.parent_id,
            keywords=tuple(row.keywords),
            summary=row.summary,
        )
        for row in rows
    )


def _memory_views(session: Session, run_id: str) -> tuple[MemoryView, ...]:
    rows = session.scalars(select(Memory).where(Memory.extraction_run_id == run_id).order_by(Memory.id)).all()
    return tuple(_memory_view(session, row) for row in rows)


def _memory_view(session: Session, row: Memory) -> MemoryView:
    return MemoryView(
        id=row.id,
        kind=row.kind,
        text=row.text,
        topic_ids=_ids(session, select(MemoryTopic.topic_id).where(MemoryTopic.memory_id == row.id)),
        message_ids=_ids(session, select(MemorySource.message_id).where(MemorySource.memory_id == row.id)),
        confidence=row.confidence,
    )


def _entity_views(session: Session, run_id: str) -> tuple[EntityView, ...]:
    rows = session.scalars(select(Entity).where(Entity.extraction_run_id == run_id).order_by(Entity.name)).all()
    return tuple(_entity_view(session, row) for row in rows)


def _entity_view(session: Session, row: Entity) -> EntityView:
    return EntityView(
        id=row.id,
        name=row.name,
        entity_type=row.entity_type,
        message_ids=_ids(session, select(EntitySource.message_id).where(EntitySource.entity_id == row.id)),
    )


def _message_views(session: Session, conversation_id: str) -> tuple[MessageView, ...]:
    return tuple(
        MessageView(
            id=row.id,
            speaker=row.speaker,
            content=row.content,
            position=row.position,
            source_id=row.source_id,
            timestamp=ensure_utc(row.timestamp),
        )
        for row in list_messages(session, conversation_id)
    )


def _relation_views(session: Session, run_id: str) -> tuple[RelationView, ...]:
    rows = session.scalars(
        select(GraphRelationship).where(GraphRelationship.extraction_run_id == run_id).order_by(GraphRelationship.id)
    ).all()
    return tuple(_relation_view(row) for row in rows)


def _relation_view(row: GraphRelationship) -> RelationView:
    return RelationView(
        id=row.id,
        relation_type=row.relation_type,
        source_type=row.source_type,
        source_id=row.source_id,
        target_type=row.target_type,
        target_id=row.target_id,
        evidence_message_ids=tuple(row.evidence_message_ids),
    )


def _memory_detail(session: Session, memory: Memory, run: ExtractionRun) -> MemoryDetail:
    return MemoryDetail(
        id=memory.id,
        conversation_id=memory.conversation_id,
        extraction_run_id=run.id,
        provider=run.provider,
        kind=memory.kind,
        text=memory.text,
        confidence=memory.confidence,
        topics=_topic_briefs(session, memory.id),
        source_messages=_source_messages(session, memory.id),
        relationships=_memory_relationships(session, memory),
    )


def _topic_briefs(session: Session, memory_id: str) -> list[TopicBrief]:
    topic_ids = _ids(session, select(MemoryTopic.topic_id).where(MemoryTopic.memory_id == memory_id))
    if not topic_ids:
        return []
    rows = session.scalars(select(Topic).where(Topic.id.in_(topic_ids)).order_by(Topic.label)).all()
    return [TopicBrief(id=row.id, label=row.label, parent_id=row.parent_id) for row in rows]


def _source_messages(session: Session, memory_id: str) -> list[MessageOut]:
    message_ids = _ids(session, select(MemorySource.message_id).where(MemorySource.memory_id == memory_id))
    if not message_ids:
        return []
    rows = session.scalars(select(Message).where(Message.id.in_(message_ids)).order_by(Message.position)).all()
    return [_message_out(row) for row in rows]


def _memory_relationships(session: Session, memory: Memory) -> list[RelationshipOut]:
    statement = select(GraphRelationship).where(
        GraphRelationship.extraction_run_id == memory.extraction_run_id,
        or_(GraphRelationship.source_id == memory.id, GraphRelationship.target_id == memory.id),
    )
    return [_relationship_out(session, memory.id, row) for row in session.scalars(statement).all()]


def _relationship_out(session: Session, memory_id: str, row: GraphRelationship) -> RelationshipOut:
    outgoing = row.source_id == memory_id
    other_type = row.target_type if outgoing else row.source_type
    other_id = row.target_id if outgoing else row.source_id
    return RelationshipOut(
        id=row.id,
        type=row.relation_type,
        direction="outgoing" if outgoing else "incoming",
        other_type=other_type,
        other_id=other_id,
        other_label=_label(session, other_type, other_id),
    )


def _topic_out(session: Session, topic: Topic) -> TopicOut:
    memory_count = len(_ids(session, select(MemoryTopic.memory_id).where(MemoryTopic.topic_id == topic.id)))
    return TopicOut(
        id=topic.id,
        conversation_id=topic.conversation_id,
        parent_id=topic.parent_id,
        label=topic.label,
        keywords=list(topic.keywords),
        summary=topic.summary,
        memory_count=memory_count,
    )


def _runs(session: Session, conversation_id: str | None) -> list[ExtractionRun]:
    if conversation_id is not None:
        _require_conversation(session, conversation_id)
        run = latest_run(session, conversation_id)
        return [run] if run else []
    found: list[ExtractionRun] = []
    for conversation_id in session.scalars(select(Conversation.id)).all():
        run = latest_run(session, conversation_id)
        if run is not None:
            found.append(run)
    return found


def _label(session: Session, node_type: str, node_id: str) -> str:
    if node_type in {"topic", "subtopic"}:
        row = session.get(Topic, node_id)
        return row.label if row else node_id
    if node_type in {"memory", "decision"}:
        row = session.get(Memory, node_id)
        return row.text if row else node_id
    if node_type == "entity":
        row = session.get(Entity, node_id)
        return row.name if row else node_id
    message = session.get(Message, node_id)
    if message is None:
        return node_id
    return f"{message.speaker}: {message.content}"


def _ids(session: Session, statement) -> tuple[str, ...]:
    return tuple(session.scalars(statement).all())


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        source_id=message.source_id,
        speaker=message.speaker,
        content=message.content,
        position=message.position,
        timestamp=ensure_utc(message.timestamp),
    )


def _require_conversation(session: Session, conversation_id: str) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise AppError(404, "Conversation not found.")
    return conversation


def _empty_graph(conversation_id: str) -> GraphOut:
    return GraphOut(
        conversation_id=conversation_id,
        extraction_run_id=None,
        provider=None,
        limitations=[],
        nodes=[],
        edges=[],
    )
