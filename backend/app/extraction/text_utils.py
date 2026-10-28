"""Token and sentence helpers for the baseline extractor."""

import re

from app.constants import MIN_SENTENCE_WORDS

STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "we", "i",
        "is", "are", "was", "were", "be", "been", "before", "over", "with", "that",
        "this", "it", "at", "per", "should", "will", "has", "have", "from", "by",
        "our", "your", "their", "they", "you", "me", "my", "but", "if", "so", "do",
        "does", "did", "not", "no", "yes", "can", "cannot", "under", "into", "than",
        "then", "also", "just", "about", "as", "its", "it's", "let", "want", "cover",
        "plan", "decided", "decision", "agreed", "prefer", "preference", "rather",
        "depends", "actually", "earlier", "supersedes", "supersede", "must",
        "required", "requirement", "think", "believe", "probably", "maybe", "might",
        "seems", "constraint", "said", "include", "finish", "block", "hard", "raw",
        "text", "items", "steps", "short", "public", "page", "mention", "length",
        "stays", "stay", "include", "dollars",
    }
)
CAPITALIZED_STOP = frozenset(
    {"The", "This", "That", "Earlier", "Actually", "We", "I", "A", "An", "And"}
)
SENTENCE_SPLIT = re.compile(r"[^.!?]+[.!?]?")
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{2,}")
CAPITALIZED_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
BUT_SPLIT = re.compile(r",\s+but\s+", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries and on ', but' contrasts."""
    pieces: list[str] = []
    for rough in SENTENCE_SPLIT.findall(text):
        pieces.extend(BUT_SPLIT.split(rough))
    return [piece.strip(" ,") for piece in pieces if piece.strip(" ,")]


def word_count(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())


def usable_sentence(text: str) -> bool:
    """Return whether a sentence is long enough to store as a memory."""
    return word_count(text) >= MIN_SENTENCE_WORDS


def tokens(text: str) -> list[str]:
    """Return significant lowercase tokens in order."""
    return [token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in STOPWORDS]


def phrases(text: str) -> set[str]:
    """Return unigrams and adjacent bigrams for topic discovery."""
    words = tokens(text)
    found = set(words)
    found.update(f"{left} {right}" for left, right in zip(words, words[1:]))
    return found


def phrase_in_text(phrase: str, text: str) -> bool:
    """Return whether `phrase` appears as whole words, case-insensitively.

    A trailing symbol such as `+` in `C++` still ends the match. Ordinary words
    keep a word boundary, so `Tim` does not match inside `timeline`.
    """
    if not phrase:
        return False
    body = r"\s+".join(re.escape(part) for part in phrase.split())
    leading = r"\b" if phrase[0].isalnum() else r"(?<!\w)"
    trailing = r"\b" if phrase[-1].isalnum() else r"(?!\w)"
    return re.search(leading + body + trailing, text, flags=re.IGNORECASE) is not None


def title_phrase(phrase: str) -> str:
    """Format a keyword phrase as a short topic label."""
    return " ".join(part.capitalize() for part in phrase.split())


def slug(text: str) -> str:
    """Build a stable key fragment."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def capitalized_mentions(text: str) -> list[str]:
    """Return mid-sentence capitalized names, skipping sentence-initial words."""
    mentions: list[str] = []
    for match in CAPITALIZED_PATTERN.finditer(text):
        if _starts_sentence(text, match.start()):
            continue
        name = match.group(1)
        if name in CAPITALIZED_STOP:
            continue
        mentions.append(name)
    return mentions


def _starts_sentence(text: str, index: int) -> bool:
    if index == 0:
        return True
    prefix = text[max(0, index - 2) : index]
    return prefix.endswith(". ") or prefix.endswith("? ") or prefix.endswith("! ")


def shared_tokens(left: str, right: str) -> set[str]:
    """Return significant tokens that appear in both statements."""
    return set(tokens(left)) & set(tokens(right))


def name_in_text(name: str, text: str) -> bool:
    """Return whether `name` appears as a whole word or phrase."""
    if not name.strip():
        return False
    pattern = r"\b" + re.escape(name.strip()) + r"\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None
