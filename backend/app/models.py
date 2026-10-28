"""Persistence models.

Table shapes use portable SQLAlchemy types so the same models can move to
PostgreSQL by changing DATABASE_URL and adding a PostgreSQL driver. Original
messages stay independent of extracted memories. A new extraction run appends
rows and leaves earlier decisions in place.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Conversation(Base):
    """Imported conversation header."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    """Original utterance, stored separately from extracted memory."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    source_id: Mapped[str | None] = mapped_column(String(200))
    speaker: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ExtractionRun(Base):
    """One extraction pass. Later passes do not delete earlier rows."""

    __tablename__ = "extraction_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Topic(Base):
    """Topic or subtopic produced by an extraction run."""

    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)


class Memory(Base):
    """Extracted statement. Conflicting memories are stored side by side."""

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None]


class MemoryTopic(Base):
    """Many-to-many link so one memory can belong to several topics."""

    __tablename__ = "memory_topics"

    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), primary_key=True)


class MemorySource(Base):
    """Provenance from an extracted memory back to an original message."""

    __tablename__ = "memory_sources"

    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id"), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)


class Entity(Base):
    """Named entity observed in the conversation."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)


class EntitySource(Base):
    """Message that contained an entity mention."""

    __tablename__ = "entity_sources"

    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)


class GraphRelationship(Base):
    """Explicit relationship between two graph endpoints."""

    __tablename__ = "graph_relationships"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "relation_type",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            name="uq_relationship_endpoint",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evidence_message_ids: Mapped[list] = mapped_column(JSON, nullable=False)
