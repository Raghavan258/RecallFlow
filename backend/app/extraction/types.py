"""Provider-neutral extraction records, validated before persistence."""

from pydantic import BaseModel, Field

from app.constants import MEMORY_KINDS, NODE_TYPES, RELATION_TYPES


class MessageInput(BaseModel):
    """Message passed into an extractor. Timestamps stay absent when unknown."""

    id: str
    speaker: str
    content: str
    position: int
    source_id: str | None = None


class ExtractedTopic(BaseModel):
    """Topic identified by a provider-local key."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=200)
    parent_key: str | None = None
    keywords: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)


class ExtractedMemory(BaseModel):
    """Statement tied to one or more topics and source messages."""

    key: str = Field(min_length=1)
    kind: str
    text: str = Field(min_length=1)
    topic_keys: list[str] = Field(default_factory=list)
    message_ids: list[str] = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExtractedEntity(BaseModel):
    """Entity observed in one or more messages."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=32)
    message_ids: list[str] = Field(min_length=1)


class ExtractedRelationship(BaseModel):
    """Relationship between two keys in the same extraction result."""

    relation_type: str
    source_type: str
    source_key: str
    target_type: str
    target_key: str
    evidence_message_ids: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Full extractor output."""

    provider: str
    limitations: list[str]
    topics: list[ExtractedTopic]
    memories: list[ExtractedMemory]
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]


def memory_endpoint_type(kind: str) -> str:
    """Decision statements use their own graph node type."""
    if kind == "decision":
        return "decision"
    return "memory"


def allowed_kind(kind: str) -> bool:
    """Return whether `kind` is a known memory kind."""
    return kind in MEMORY_KINDS


def allowed_node(node_type: str) -> bool:
    """Return whether `node_type` can appear on a relationship."""
    return node_type in NODE_TYPES


def allowed_relation(relation_type: str) -> bool:
    """Return whether `relation_type` is a supported relationship."""
    return relation_type in RELATION_TYPES
