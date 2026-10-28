"""Normalize paste transcripts and JSON messages before storage."""

import re
from datetime import datetime

from app.constants import DEFAULT_TITLE, MAX_CONTENT_LENGTH, MAX_MESSAGES, MAX_SPEAKER_LENGTH
from app.errors import AppError
from app.schemas import ImportMessageIn, ImportRequest
from app.services.clock import ensure_utc

LINE_PATTERN = re.compile(
    r"^(?P<speaker>[^:\[\]\n]{1,80}?)(?:\s*\[(?P<timestamp>[^\]]+)\])?\s*:\s*(?P<content>.*)$"
)
PROTOCOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
CLOCK_PATTERN = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]m)?\b", re.IGNORECASE)
ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


class ParsedMessage:
    """Message ready to insert. Missing timestamps stay unset."""

    def __init__(
        self,
        speaker: str,
        content: str,
        source_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        self.speaker = speaker
        self.content = content
        self.source_id = source_id
        self.timestamp = timestamp


def normalize_import(payload: ImportRequest) -> tuple[str, str, list[ParsedMessage]]:
    """Return title, source format, and ordered messages."""
    title = _title(payload.title)
    if payload.messages:
        return title, "json", _from_messages(payload.messages)
    return title, "paste", parse_transcript(payload.transcript or "")


def parse_transcript(transcript: str) -> list[ParsedMessage]:
    """Parse `Speaker: text` lines. Continuation lines extend the previous message."""
    parsed: list[ParsedMessage] = []
    for line_number, raw in enumerate(transcript.splitlines(), start=1):
        _consume_line(raw, line_number, parsed)
    _require_bounds(parsed)
    return parsed


def _consume_line(raw: str, line_number: int, parsed: list[ParsedMessage]) -> None:
    if not raw.strip():
        return
    match = LINE_PATTERN.match(raw.strip())
    if match is None or _continues_previous(raw):
        _append_continuation(raw, line_number, parsed)
        return
    content = match.group("content").strip()
    _require_text(content, line_number)
    parsed.append(
        ParsedMessage(
            speaker=match.group("speaker").strip(),
            content=content,
            timestamp=_timestamp(match.group("timestamp"), line_number),
        )
    )


def _continues_previous(raw: str) -> bool:
    stripped = raw.strip()
    return _matches(PROTOCOL_PATTERN, stripped) or _matches(CLOCK_PATTERN, stripped) or _matches(ISO_PATTERN, stripped)


def _matches(pattern: re.Pattern[str], value: str) -> bool:
    return pattern.match(value) is not None


def _append_continuation(raw: str, line_number: int, parsed: list[ParsedMessage]) -> None:
    if not parsed:
        raise AppError(422, f"Could not parse transcript line {line_number}.")
    parsed[-1].content = f"{parsed[-1].content}\n{raw.strip()}"
    if len(parsed[-1].content) > MAX_CONTENT_LENGTH:
        raise AppError(422, f"Message content exceeds {MAX_CONTENT_LENGTH} characters.")


def _from_messages(messages: list[ImportMessageIn]) -> list[ParsedMessage]:
    if len(messages) > MAX_MESSAGES:
        raise AppError(422, f"A conversation can include at most {MAX_MESSAGES} messages.")
    return [
        ParsedMessage(
            speaker=item.speaker.strip(),
            content=item.content.strip(),
            source_id=_clean(item.source_id),
            timestamp=ensure_utc(item.timestamp),
        )
        for item in messages
        if _require_pair(item.speaker, item.content)
    ]


def _require_pair(speaker: str, content: str) -> bool:
    if not speaker.strip() or not content.strip():
        raise AppError(422, "Each message needs a speaker and content.")
    if len(speaker.strip()) > MAX_SPEAKER_LENGTH:
        raise AppError(422, f"Speaker names must be {MAX_SPEAKER_LENGTH} characters or fewer.")
    return True


def _title(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    return DEFAULT_TITLE


def _timestamp(value: str | None, line_number: int) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return ensure_utc(parsed)
    except ValueError as exc:
        raise AppError(422, f"Invalid timestamp on line {line_number}.") from exc


def _require_text(content: str, line_number: int) -> None:
    if not content:
        raise AppError(422, f"Line {line_number} is missing message content.")
    if len(content) > MAX_CONTENT_LENGTH:
        raise AppError(422, f"Message content exceeds {MAX_CONTENT_LENGTH} characters.")


def _require_bounds(parsed: list[ParsedMessage]) -> None:
    if not parsed:
        raise AppError(422, "Transcript did not contain any messages.")
    if len(parsed) > MAX_MESSAGES:
        raise AppError(422, f"A conversation can include at most {MAX_MESSAGES} messages.")


def _clean(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
