"""Sentence classification for the baseline extractor."""

import re

from app.constants import BASELINE_CONFIDENCE
from app.extraction.text_utils import split_sentences, usable_sentence
from app.extraction.topics import matching_topic_keys
from app.extraction.types import ExtractedMemory, ExtractedTopic, MessageInput

CLASSIFIERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("question", re.compile(r"\?\s*$")),
    ("decision", re.compile(r"\b(decided|decision|we will|we'll|let's|agreed|supersedes|supersede)\b", re.I)),
    ("preference", re.compile(r"\b(prefer|preference|rather)\b", re.I)),
    ("requirement", re.compile(r"\b(must|required|requirement|need to|needs to|shall)\b", re.I)),
    ("constraint", re.compile(r"\b(cannot|can't|constraint|limit|at most|no more than)\b", re.I)),
    ("claim", re.compile(r"\b(think|believe|probably|might|maybe|seems|actually|no longer|contradicts?)\b", re.I)),
    ("fact", re.compile(r"\b(is|are|was|were|has|have|will be|stays|depends on)\b", re.I)),
)


def build_memories(messages: list[MessageInput], topics: list[ExtractedTopic]) -> list[ExtractedMemory]:
    """Classify usable sentences and attach every matching topic."""
    memories: list[ExtractedMemory] = []
    for message in messages:
        memories.extend(_message_memories(message, topics, len(memories)))
    return memories


def _message_memories(
    message: MessageInput,
    topics: list[ExtractedTopic],
    start_index: int,
) -> list[ExtractedMemory]:
    extracted: list[ExtractedMemory] = []
    for sentence in split_sentences(message.content):
        kind = _classify(sentence)
        if kind is None or not usable_sentence(sentence):
            continue
        extracted.append(_memory(sentence, kind, message, topics, start_index + len(extracted)))
    return extracted


def _classify(sentence: str) -> str | None:
    for kind, pattern in CLASSIFIERS:
        if pattern.search(sentence):
            return kind
    return None


def _memory(
    sentence: str,
    kind: str,
    message: MessageInput,
    topics: list[ExtractedTopic],
    index: int,
) -> ExtractedMemory:
    topic_keys = matching_topic_keys(sentence, topics)
    text = sentence if sentence.endswith((".", "?", "!")) else f"{sentence}."
    return ExtractedMemory(
        key=f"memory:{index}",
        kind=kind,
        text=text,
        topic_keys=topic_keys,
        message_ids=[message.id],
        confidence=BASELINE_CONFIDENCE,
    )
