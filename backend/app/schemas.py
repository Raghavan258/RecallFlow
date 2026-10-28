"""API request and response models."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.constants import MAX_CONTENT_LENGTH, MAX_SPEAKER_LENGTH, MAX_TITLE_LENGTH


class ImportMessageIn(BaseModel):
    """One message in a JSON conversation import."""

    speaker: str = Field(min_length=1, max_length=MAX_SPEAKER_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    source_id: str | None = Field(default=None, max_length=200)
    timestamp: datetime | None = None


class ImportRequest(BaseModel):
    """Paste transcript or structured messages, but not both."""

    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH)
    transcript: str | None = Field(default=None, max_length=500_000)
    messages: list[ImportMessageIn] | None = None

    @model_validator(mode="after")
    def require_one_source(self) -> "ImportRequest":
        """Reject empty imports and imports that mix both source shapes."""
        has_transcript = bool(self.transcript and self.transcript.strip())
        has_messages = bool(self.messages)
        if has_transcript == has_messages:
            raise ValueError("Provide either a transcript or a messages array.")
        return self


class MessageOut(BaseModel):
    """Original message returned to clients.

    `timestamp` is ISO-8601 UTC with a `Z` suffix when the import provided one.
    A JSON null means the source omitted it. Offsets are converted to the same
    instant before storage; the column itself is unchanged.
    """

    id: str
    source_id: str | None
    speaker: str
    content: str
    position: int
    timestamp: datetime | None


class ConversationDetail(BaseModel):
    """Conversation plus its original messages in stored order.

    `created_at` uses the same ISO-8601 UTC `Z` form as message timestamps.
    """

    id: str
    title: str
    source_format: str
    created_at: datetime
    messages: list[MessageOut]


class ConversationSummary(BaseModel):
    """List row with counts for the latest extraction run."""

    id: str
    title: str
    created_at: datetime
    message_count: int
    topic_count: int
    memory_count: int
    relationship_count: int
    provider: str | None


class Counts(BaseModel):
    """Aggregate counts across stored conversations."""

    conversations: int
    topics: int
    memories: int
    relationships: int


class ConversationListResponse(BaseModel):
    """Conversation index used by the dashboard."""

    items: list[ConversationSummary]
    totals: Counts


class TopicOut(BaseModel):
    """Topic shown in the sidebar."""

    id: str
    conversation_id: str
    parent_id: str | None
    label: str
    keywords: list[str]
    summary: str
    memory_count: int


class GraphNodeOut(BaseModel):
    """Node in a conversation graph."""

    id: str
    type: str
    label: str
    initially_visible: bool
    topic_ids: list[str]
    payload: dict


class GraphEdgeOut(BaseModel):
    """Stored relationship projected as a graph edge."""

    id: str
    type: str
    source: str
    target: str
    source_type: str
    target_type: str
    evidence_message_ids: list[str]


class GraphOut(BaseModel):
    """Graph for one extraction run."""

    conversation_id: str
    extraction_run_id: str | None
    provider: str | None
    limitations: list[str]
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class TopicBrief(BaseModel):
    """Topic reference nested under a memory."""

    id: str
    label: str
    parent_id: str | None


class RelationshipOut(BaseModel):
    """Relationship that touches a selected memory."""

    id: str
    type: str
    direction: str
    other_type: str
    other_id: str
    other_label: str


class MemoryDetail(BaseModel):
    """Memory with topics and the original messages that support it."""

    id: str
    conversation_id: str
    extraction_run_id: str
    provider: str
    kind: str
    text: str
    confidence: float | None
    topics: list[TopicBrief]
    source_messages: list[MessageOut]
    relationships: list[RelationshipOut]


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str


class RetrievalRequest(BaseModel):
    """Question against one stored conversation. This does not ask for an answer."""

    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="graph", pattern="^(keyword|graph|budget)$")
    token_budget: int = Field(default=180, ge=0, le=8000)
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum ranked candidates considered before packing. Discarded candidates are not replaced.",
    )

    @model_validator(mode="after")
    def question_has_text(self) -> "RetrievalRequest":
        """Reject a question that is only whitespace."""
        if not self.question.strip():
            raise ValueError("Question is required.")
        return self


class RetrievalEvidence(BaseModel):
    """One ranked memory and the original messages that support it."""

    memory_id: str
    text: str
    topic_ids: list[str]
    topic_labels: list[str]
    source_message_ids: list[str]
    source_ids: list[str]
    score: float
    explanation: str
    selected: bool
    sources: list[MessageOut]


class TokenUsage(BaseModel):
    """Budget accounting for the configured whitespace tokenizer."""

    budget: int
    selected: int
    discarded: int


class RetrievalResponse(BaseModel):
    """Ranked evidence, source messages, and token usage. Not an answer."""

    conversation_id: str
    extraction_run_id: str
    question: str
    mode: str
    evidence: list[RetrievalEvidence]
    topics: list[str]
    token_usage: TokenUsage
    latency_ms: float
