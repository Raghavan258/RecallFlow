"""Shared limits and vocabularies."""

DEFAULT_TITLE = "Untitled conversation"
LABEL_LIMIT = 90
MAX_MESSAGES = 400
MAX_CONTENT_LENGTH = 20000
MAX_TITLE_LENGTH = 200
MAX_SPEAKER_LENGTH = 80
MIN_SENTENCE_WORDS = 4
MIN_TOPIC_DOCUMENT_FREQUENCY = 2
MAX_ROOT_TOPICS = 6
MAX_SUBTOPICS_PER_PARENT = 2
TOPIC_JACCARD_LIMIT = 0.8
BASELINE_CONFIDENCE = 0.45
MIN_SHARED_CORRECTION_TOKENS = 2
DEFAULT_TOKEN_BUDGET = 180
DEFAULT_RETRIEVAL_LIMIT = 5
MAX_GRAPH_CANDIDATES = 12
GRAPH_EDGE_BONUS = 0.15
CORRECTION_SOURCE_BONUS = 0.2
RETRIEVAL_MODES = ("keyword", "graph", "budget")
STRONG_MEMORY_RELATIONS = ("SUPERSEDES", "CONTRADICTS", "SUPPORTS")
SUMMARY_LIMIT = 180

MEMORY_KINDS = (
    "fact",
    "claim",
    "decision",
    "preference",
    "requirement",
    "constraint",
    "question",
)
NODE_TYPES = ("topic", "subtopic", "memory", "entity", "decision", "message")
RELATION_TYPES = (
    "CONTAINS",
    "RELATED_TO",
    "MENTIONS",
    "SUPPORTS",
    "DEPENDS_ON",
    "SUPERSEDES",
    "CONTRADICTS",
    "DERIVED_FROM",
)
SOURCE_FORMATS = ("paste", "json")
PROVIDERS = ("baseline", "llm")

BASELINE_LIMITATIONS = (
    "Topics come from repeated keywords, so paraphrases of the same idea may split or merge.",
    "Memories are sentences matched to cue phrases, not a full reading of intent.",
    "A sentence is stored only when it matches a fact, claim, decision, preference, requirement, constraint, or question cue.",
    "A correction edge needs an explicit cue and at least two shared content words, and it may point at an earlier message.",
    "Relationships are recorded only from shared sources or explicit cues such as depends on, supersedes, or actually.",
    "Entity detection keeps mid-sentence capitalized names and can miss pronouns or lowercase products.",
)
