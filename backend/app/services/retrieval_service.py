"""Load the latest extraction run and rank memories for a question."""

from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_RETRIEVAL_LIMIT, DEFAULT_TOKEN_BUDGET
from app.errors import AppError
from app.models import GraphRelationship, Memory, MemorySource, MemoryTopic, Message, Topic
from app.retrieval.engine import retrieve
from app.retrieval.types import RetrievalCorpus, RetrievalEdge, RetrievalMemory, RetrievalPack, RetrievalTopic
from app.schemas import MessageOut, RetrievalEvidence, RetrievalResponse, TokenUsage
from app.services.clock import ensure_utc
from app.services.conversations import latest_run
from app.services.graph_service import _require_conversation


def retrieve_conversation(
    session: Session,
    conversation_id: str,
    question: str,
    mode: str,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
) -> RetrievalResponse:
    """Return ranked evidence for the latest run. Missing runs are an error."""
    _require_conversation(session, conversation_id)
    run = latest_run(session, conversation_id)
    if run is None:
        raise AppError(422, "Extract the conversation before asking a question.")
    started = perf_counter()
    corpus, messages = _corpus(session, conversation_id, run.id)
    pack = retrieve(corpus, question, mode, limit=limit, token_budget=token_budget)
    latency_ms = round((perf_counter() - started) * 1000, 3)
    return _response(conversation_id, run.id, question, pack, messages, latency_ms)


def _corpus(session: Session, conversation_id: str, run_id: str) -> tuple[RetrievalCorpus, dict[str, Message]]:
    message_rows = session.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.position)
    )
    messages = {item.id: item for item in message_rows}
    topics = list(session.scalars(select(Topic).where(Topic.extraction_run_id == run_id).order_by(Topic.id)))
    labels = {item.id: item.label for item in topics}
    membership = _membership(session, run_id)
    stored = session.scalars(select(Memory).where(Memory.extraction_run_id == run_id).order_by(Memory.id))
    memories = tuple(_memory(item, membership, labels, messages) for item in stored)
    edges = tuple(
        RetrievalEdge(relation_type=item.relation_type, source_id=item.source_id, target_id=item.target_id)
        for item in session.scalars(
            select(GraphRelationship).where(GraphRelationship.extraction_run_id == run_id).order_by(GraphRelationship.id)
        )
    )
    topic_rows = tuple(RetrievalTopic(id=item.id, label=item.label, keywords=tuple(item.keywords)) for item in topics)
    return RetrievalCorpus(memories=memories, topics=topic_rows, edges=edges), messages


def _membership(session: Session, run_id: str) -> dict[str, tuple[list[str], list[str]]]:
    found: dict[str, tuple[list[str], list[str]]] = {}
    memory_ids = list(session.scalars(select(Memory.id).where(Memory.extraction_run_id == run_id)))
    for memory_id in memory_ids:
        topics = list(
            session.scalars(
                select(MemoryTopic.topic_id).where(MemoryTopic.memory_id == memory_id).order_by(MemoryTopic.topic_id)
            )
        )
        sources = list(
            session.scalars(
                select(MemorySource.message_id)
                .join(Message, Message.id == MemorySource.message_id)
                .where(MemorySource.memory_id == memory_id)
                .order_by(Message.position)
            )
        )
        found[memory_id] = (topics, sources)
    return found


def _memory(
    memory: Memory,
    membership: dict[str, tuple[list[str], list[str]]],
    labels: dict[str, str],
    messages: dict[str, Message],
) -> RetrievalMemory:
    topic_ids, message_ids = membership.get(memory.id, ([], []))
    return RetrievalMemory(
        id=memory.id,
        text=memory.text,
        topic_ids=tuple(topic_ids),
        topic_labels=tuple(labels.get(topic_id, topic_id) for topic_id in topic_ids),
        message_ids=tuple(message_ids),
        source_ids=tuple(_source_id(messages.get(message_id), message_id) for message_id in message_ids),
    )


def _source_id(message: Message | None, message_id: str) -> str:
    if message is None or not message.source_id:
        return message_id
    return message.source_id


def _response(
    conversation_id: str,
    run_id: str,
    question: str,
    pack: RetrievalPack,
    messages: dict[str, Message],
    latency_ms: float,
) -> RetrievalResponse:
    evidence = [_evidence(item, messages) for item in pack.evidence]
    return RetrievalResponse(
        conversation_id=conversation_id,
        extraction_run_id=run_id,
        question=question,
        mode=pack.mode,
        evidence=evidence,
        topics=sorted({label for item in pack.evidence if item.selected for label in item.memory.topic_labels}),
        token_usage=TokenUsage(budget=pack.token_budget, selected=pack.selected_tokens, discarded=pack.discarded),
        latency_ms=latency_ms,
    )


def _evidence(item, messages: dict[str, Message]) -> RetrievalEvidence:
    return RetrievalEvidence(
        memory_id=item.memory.id,
        text=item.memory.text,
        topic_ids=list(item.memory.topic_ids),
        topic_labels=list(item.memory.topic_labels),
        source_message_ids=list(item.memory.message_ids),
        source_ids=list(item.memory.source_ids),
        score=item.score,
        explanation=item.explanation,
        selected=item.selected,
        sources=[_message_out(messages[message_id]) for message_id in item.memory.message_ids if message_id in messages],
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
