"""Retrieval records. The engine reads these and does not touch the database."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMemory:
    """One stored memory and the source identifiers behind it."""

    id: str
    text: str
    topic_ids: tuple[str, ...]
    topic_labels: tuple[str, ...]
    message_ids: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalTopic:
    """Topic keywords used to decide whether a query names that topic."""

    id: str
    label: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalEdge:
    """Stored relationship. Endpoints are topic or memory ids."""

    relation_type: str
    source_id: str
    target_id: str


@dataclass(frozen=True)
class RetrievalCorpus:
    """Latest extraction run projected for retrieval."""

    memories: tuple[RetrievalMemory, ...]
    topics: tuple[RetrievalTopic, ...]
    edges: tuple[RetrievalEdge, ...]


@dataclass(frozen=True)
class RankedMemory:
    """A candidate memory with a score and a short explanation."""

    memory: RetrievalMemory
    score: float
    explanation: str
    selected: bool


@dataclass(frozen=True)
class RetrievalPack:
    """Ranked evidence plus token accounting. This is not an answer."""

    mode: str
    evidence: tuple[RankedMemory, ...]
    token_budget: int
    selected_tokens: int
    discarded: int
