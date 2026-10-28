"""Build a retrieval corpus from an extraction result or from stored rows."""

from app.extraction.types import ExtractionResult, MessageInput
from app.retrieval.types import RetrievalCorpus, RetrievalEdge, RetrievalMemory, RetrievalTopic


def corpus_from_result(messages: list[MessageInput], result: ExtractionResult) -> RetrievalCorpus:
    """Project an in-memory extraction into retrieval records. Keys stay the ids."""
    source_of = {item.id: item.source_id or item.id for item in messages}
    labels = {topic.key: topic.label for topic in result.topics}
    memories = tuple(_memory(item, labels, source_of) for item in result.memories)
    topics = tuple(RetrievalTopic(id=item.key, label=item.label, keywords=tuple(item.keywords)) for item in result.topics)
    edges = tuple(
        RetrievalEdge(relation_type=item.relation_type, source_id=item.source_key, target_id=item.target_key)
        for item in result.relationships
    )
    return RetrievalCorpus(memories=memories, topics=topics, edges=edges)


def _memory(item, labels: dict[str, str], source_of: dict[str, str]) -> RetrievalMemory:
    return RetrievalMemory(
        id=item.key,
        text=item.text,
        topic_ids=tuple(item.topic_keys),
        topic_labels=tuple(labels.get(key, key) for key in item.topic_keys),
        message_ids=tuple(item.message_ids),
        source_ids=tuple(source_of.get(message_id, message_id) for message_id in item.message_ids),
    )
