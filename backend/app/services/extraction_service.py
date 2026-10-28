"""Run an extractor and append a new extraction run."""

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, ExtractionError
from app.extraction.types import ExtractionResult, MessageInput
from app.extraction.validate import validate_extraction
from app.models import (
    Entity,
    EntitySource,
    ExtractionRun,
    GraphRelationship,
    Memory,
    MemorySource,
    MemoryTopic,
    Topic,
)
from app.services.conversations import list_messages


class ExtractionProvider:
    """Provider interface implemented by the baseline and LLM extractors."""

    def extract(self, messages: list[MessageInput]) -> ExtractionResult:
        """Return a structured extraction for these messages."""
        raise NotImplementedError


def extract_conversation(
    session: Session,
    conversation_id: str,
    provider: ExtractionProvider,
    clock: Callable[[], datetime],
) -> ExtractionRun:
    """Validate provider output and append it. Earlier runs stay stored."""
    from app.models import Conversation

    if session.get(Conversation, conversation_id) is None:
        raise AppError(404, "Conversation not found.")
    messages = list_messages(session, conversation_id)
    inputs = [_input(item) for item in messages]
    try:
        result = validate_extraction(provider.extract(inputs), {item.id for item in messages})
        run = persist_extraction(session, conversation_id, result, clock())
        session.commit()
    except AppError:
        session.rollback()
        raise
    return run


def persist_extraction(
    session: Session,
    conversation_id: str,
    result: ExtractionResult,
    created_at: datetime,
) -> ExtractionRun:
    """Insert one extraction run and its graph records."""
    run = ExtractionRun(
        id=str(uuid4()),
        conversation_id=conversation_id,
        provider=result.provider,
        limitations=result.limitations,
        created_at=created_at,
    )
    session.add(run)
    session.flush()
    topic_ids = _save_topics(session, run, result)
    memory_ids = _save_memories(session, run, result, topic_ids)
    entity_ids = _save_entities(session, run, result)
    _save_relationships(session, run, result, topic_ids, memory_ids, entity_ids)
    return run


def _save_topics(session: Session, run: ExtractionRun, result: ExtractionResult) -> dict[str, str]:
    pending = list(result.topics)
    saved: dict[str, str] = {}
    while pending:
        ready = [topic for topic in pending if topic.parent_key is None or topic.parent_key in saved]
        if not ready:
            raise ExtractionError("Topic parents could not be ordered.")
        for topic in ready:
            saved[topic.key] = _insert_topic(session, run, topic, saved.get(topic.parent_key or ""))
        pending = [topic for topic in pending if topic.key not in saved]
    return saved


def _insert_topic(session: Session, run: ExtractionRun, topic, parent_id: str | None) -> str:
    row = Topic(
        id=str(uuid4()),
        extraction_run_id=run.id,
        conversation_id=run.conversation_id,
        parent_id=parent_id,
        label=topic.label,
        keywords=topic.keywords,
        summary=topic.summary,
    )
    session.add(row)
    session.flush()
    return row.id


def _save_memories(
    session: Session,
    run: ExtractionRun,
    result: ExtractionResult,
    topic_ids: dict[str, str],
) -> dict[str, str]:
    saved: dict[str, str] = {}
    for item in result.memories:
        saved[item.key] = _insert_memory(session, run, item, topic_ids)
    return saved


def _insert_memory(session: Session, run: ExtractionRun, item, topic_ids: dict[str, str]) -> str:
    row = Memory(
        id=str(uuid4()),
        extraction_run_id=run.id,
        conversation_id=run.conversation_id,
        kind=item.kind,
        text=item.text,
        confidence=item.confidence,
    )
    session.add(row)
    session.flush()
    for key in item.topic_keys:
        session.add(MemoryTopic(memory_id=row.id, topic_id=topic_ids[key]))
    for message_id in item.message_ids:
        session.add(MemorySource(memory_id=row.id, message_id=message_id))
    return row.id


def _save_entities(session: Session, run: ExtractionRun, result: ExtractionResult) -> dict[str, str]:
    saved: dict[str, str] = {}
    for item in result.entities:
        saved[item.key] = _insert_entity(session, run, item)
    return saved


def _insert_entity(session: Session, run: ExtractionRun, item) -> str:
    row = Entity(
        id=str(uuid4()),
        extraction_run_id=run.id,
        conversation_id=run.conversation_id,
        name=item.name,
        entity_type=item.entity_type,
    )
    session.add(row)
    session.flush()
    for message_id in item.message_ids:
        session.add(EntitySource(entity_id=row.id, message_id=message_id))
    return row.id


def _save_relationships(
    session: Session,
    run: ExtractionRun,
    result: ExtractionResult,
    topic_ids: dict[str, str],
    memory_ids: dict[str, str],
    entity_ids: dict[str, str],
) -> None:
    lookup = {"topic": topic_ids, "subtopic": topic_ids, "memory": memory_ids, "decision": memory_ids, "entity": entity_ids}
    for item in result.relationships:
        session.add(_relationship(run, item, lookup))


def _relationship(run: ExtractionRun, item, lookup: dict[str, dict[str, str]]) -> GraphRelationship:
    return GraphRelationship(
        id=str(uuid4()),
        extraction_run_id=run.id,
        conversation_id=run.conversation_id,
        relation_type=item.relation_type,
        source_type=item.source_type,
        source_id=_resolve(item.source_type, item.source_key, lookup),
        target_type=item.target_type,
        target_id=_resolve(item.target_type, item.target_key, lookup),
        evidence_message_ids=item.evidence_message_ids,
    )


def _resolve(node_type: str, key: str, lookup: dict[str, dict[str, str]]) -> str:
    if node_type == "message":
        return key
    return lookup[node_type][key]


def _input(message) -> MessageInput:
    return MessageInput(
        id=message.id,
        speaker=message.speaker,
        content=message.content,
        position=message.position,
        source_id=message.source_id,
    )
