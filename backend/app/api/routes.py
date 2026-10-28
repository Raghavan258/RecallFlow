"""HTTP routes for health, import, extraction, and graph reads."""

import json
from collections.abc import Generator
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import session_scope
from app.extraction.factory import build_provider
from app.schemas import (
    ConversationDetail,
    ConversationListResponse,
    GraphOut,
    HealthResponse,
    ImportRequest,
    MemoryDetail,
    RetrievalRequest,
    RetrievalResponse,
    TopicOut,
)
from app.services.clock import utc_now
from app.services.conversations import get_conversation, import_conversation, list_conversations
from app.services.extraction_service import extract_conversation
from app.services.graph_service import get_graph, get_memory, list_topics
from app.services.retrieval_service import retrieve_conversation

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "nimbus_launch.json"

health_router = APIRouter()
api_router = APIRouter()


def get_session(request: Request) -> Generator[Session, None, None]:
    """Yield a database session for the current application."""
    yield from session_scope(request.app.state.session_factory)


@health_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is serving requests."""
    return HealthResponse(status="ok")


@api_router.post("/conversations/import", response_model=ConversationDetail)
def import_route(payload: ImportRequest, session: Session = Depends(get_session)) -> ConversationDetail:
    """Store a pasted transcript or a JSON conversation."""
    return import_conversation(session, payload, utc_now)


@api_router.get("/conversations", response_model=ConversationListResponse)
def conversations_route(session: Session = Depends(get_session)) -> ConversationListResponse:
    """List stored conversations and dashboard counts."""
    return list_conversations(session)


@api_router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_route(conversation_id: str, session: Session = Depends(get_session)) -> ConversationDetail:
    """Return original messages for one conversation."""
    return get_conversation(session, conversation_id)


@api_router.post("/conversations/{conversation_id}/extract", response_model=GraphOut)
def extract_route(conversation_id: str, request: Request, session: Session = Depends(get_session)) -> GraphOut:
    """Extract topics and memories, then return the latest graph."""
    provider = build_provider(request.app.state.settings)
    extract_conversation(session, conversation_id, provider, utc_now)
    return get_graph(session, conversation_id)


@api_router.get("/conversations/{conversation_id}/graph", response_model=GraphOut)
def graph_route(conversation_id: str, session: Session = Depends(get_session)) -> GraphOut:
    """Return the graph for the latest extraction run."""
    return get_graph(session, conversation_id)


@api_router.get("/memories/{memory_id}", response_model=MemoryDetail)
def memory_route(memory_id: str, session: Session = Depends(get_session)) -> MemoryDetail:
    """Return one memory and the original messages that support it."""
    return get_memory(session, memory_id)


@api_router.get("/topics", response_model=list[TopicOut])
def topics_route(
    conversation_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[TopicOut]:
    """Return topics, optionally limited to one conversation."""
    return list_topics(session, conversation_id)


@api_router.post("/conversations/{conversation_id}/retrieve", response_model=RetrievalResponse)
def retrieve_route(
    conversation_id: str,
    payload: RetrievalRequest,
    session: Session = Depends(get_session),
) -> RetrievalResponse:
    """Rank stored memories for a question. The response is evidence, not an answer."""
    return retrieve_conversation(
        session,
        conversation_id,
        payload.question,
        payload.mode,
        token_budget=payload.token_budget,
        limit=payload.limit,
    )


@api_router.get("/sample/conversation")
def sample_route() -> JSONResponse:
    """Return the bundled sample conversation used by the dashboard."""
    return JSONResponse(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))
