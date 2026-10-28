"""Import conversations and read them back with counts."""

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Conversation, ExtractionRun, GraphRelationship, Memory, Message, Topic
from app.schemas import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    Counts,
    ImportRequest,
    MessageOut,
)
from app.services.clock import ensure_utc
from app.services.import_parser import ParsedMessage, normalize_import


def import_conversation(
    session: Session,
    payload: ImportRequest,
    clock: Callable[[], datetime],
) -> ConversationDetail:
    """Store original messages in the order they were provided."""
    title, source_format, parsed = normalize_import(payload)
    conversation = Conversation(
        id=str(uuid4()),
        title=title,
        source_format=source_format,
        created_at=clock(),
    )
    session.add(conversation)
    session.flush()
    for position, item in enumerate(parsed):
        session.add(_message(conversation.id, position, item))
    session.commit()
    return get_conversation(session, conversation.id)


def get_conversation(session: Session, conversation_id: str) -> ConversationDetail:
    """Return one conversation and its messages ordered by position."""
    conversation = _require_conversation(session, conversation_id)
    messages = list_messages(session, conversation_id)
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        source_format=conversation.source_format,
        created_at=_created_at(conversation.created_at),
        messages=[_message_out(item) for item in messages],
    )


def list_conversations(session: Session) -> ConversationListResponse:
    """List conversations with counts from each latest extraction run."""
    rows = session.scalars(select(Conversation).order_by(Conversation.created_at.desc())).all()
    items = [_summary(session, row) for row in rows]
    return ConversationListResponse(items=items, totals=_totals(items))


def list_messages(session: Session, conversation_id: str) -> list[Message]:
    """Return messages in stored order."""
    statement = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.position)
    return list(session.scalars(statement).all())


def latest_run(session: Session, conversation_id: str) -> ExtractionRun | None:
    """Return the newest extraction run for a conversation."""
    statement = (
        select(ExtractionRun)
        .where(ExtractionRun.conversation_id == conversation_id)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
    )
    return session.scalars(statement).first()


def _created_at(value: datetime) -> datetime:
    normalized = ensure_utc(value)
    if normalized is None:
        raise ValueError("Conversation created_at is missing.")
    return normalized


def _require_conversation(session: Session, conversation_id: str) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        from app.errors import AppError

        raise AppError(404, "Conversation not found.")
    return conversation


def _summary(session: Session, conversation: Conversation) -> ConversationSummary:
    run = latest_run(session, conversation.id)
    topics, memories, relationships = _run_counts(session, run.id if run else None)
    message_count = session.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        created_at=_created_at(conversation.created_at),
        message_count=int(message_count or 0),
        topic_count=topics,
        memory_count=memories,
        relationship_count=relationships,
        provider=run.provider if run else None,
    )


def _run_counts(session: Session, run_id: str | None) -> tuple[int, int, int]:
    if run_id is None:
        return 0, 0, 0
    return (
        _count(session, Topic, Topic.extraction_run_id == run_id),
        _count(session, Memory, Memory.extraction_run_id == run_id),
        _count(session, GraphRelationship, GraphRelationship.extraction_run_id == run_id),
    )


def _count(session: Session, model: type, criterion) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(criterion)) or 0)


def _totals(items: list[ConversationSummary]) -> Counts:
    return Counts(
        conversations=len(items),
        topics=sum(item.topic_count for item in items),
        memories=sum(item.memory_count for item in items),
        relationships=sum(item.relationship_count for item in items),
    )


def _message(conversation_id: str, position: int, item: ParsedMessage) -> Message:
    return Message(
        id=str(uuid4()),
        conversation_id=conversation_id,
        source_id=item.source_id,
        speaker=item.speaker,
        content=item.content,
        position=position,
        timestamp=ensure_utc(item.timestamp),
    )


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        source_id=message.source_id,
        speaker=message.speaker,
        content=message.content,
        position=message.position,
        timestamp=ensure_utc(message.timestamp),
    )
