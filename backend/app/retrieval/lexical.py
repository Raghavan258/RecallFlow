"""Keyword overlap between a question and stored memory text."""

from app.extraction.text_utils import tokens


def query_terms(question: str) -> tuple[str, ...]:
    """Return unique content tokens from the question, in first-seen order."""
    seen: list[str] = []
    for term in tokens(question):
        if term not in seen:
            seen.append(term)
    return tuple(seen)


def shared_terms(question_terms: tuple[str, ...], text: str) -> tuple[str, ...]:
    """Return question terms that also appear in `text`."""
    present = set(tokens(text))
    return tuple(term for term in question_terms if term in present)


def lexical_score(question_terms: tuple[str, ...], text: str) -> float:
    """Return the fraction of question terms found in `text`."""
    if not question_terms:
        return 0.0
    return len(shared_terms(question_terms, text)) / len(question_terms)
