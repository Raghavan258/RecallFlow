"""Deterministic extractor that does not call an external model."""

from app.constants import BASELINE_LIMITATIONS
from app.extraction.entities import build_entities
from app.extraction.memories import build_memories
from app.extraction.relations import build_relationships
from app.extraction.topics import build_topics
from app.extraction.types import ExtractedMemory, ExtractedTopic, ExtractionResult, MessageInput


def _without_unused_subtopics(
    topics: list[ExtractedTopic],
    memories: list[ExtractedMemory],
) -> tuple[list[ExtractedTopic], list[ExtractedMemory]]:
    """Drop subtopics that no memory actually mentions."""
    used = {key for memory in memories for key in memory.topic_keys}
    kept = [topic for topic in topics if topic.parent_key is None or topic.key in used]
    allowed = {topic.key for topic in kept}
    cleaned = [
        memory.model_copy(update={"topic_keys": [key for key in memory.topic_keys if key in allowed]})
        for memory in memories
    ]
    return kept, cleaned


class BaselineExtractor:
    """Keyword and cue-phrase extractor for local use without an API key."""

    def extract(self, messages: list[MessageInput]) -> ExtractionResult:
        """Extract topics, memories, entities, and evidence-backed relationships."""
        topics = build_topics(messages)
        memories = build_memories(messages, topics)
        topics, memories = _without_unused_subtopics(topics, memories)
        entities = build_entities(messages)
        return ExtractionResult(
            provider="baseline",
            limitations=list(BASELINE_LIMITATIONS),
            topics=topics,
            memories=memories,
            entities=entities,
            relationships=build_relationships(topics, memories, entities),
        )
