"""Convert public benchmark files the caller already has. This module does not download or vendor them."""

from datetime import datetime

from app.services.clock import ensure_utc

LOCOMO_LICENSE = "CC BY-NC 4.0 (snap-research/locomo). Not redistributed by RecallFlow."
LONGMEMEVAL_LICENSE = "MIT code; chat data is downloaded by the user from xiaowu0162/longmemeval-cleaned. Not redistributed here."


def adapt_locomo(sample: dict) -> tuple[dict, list[dict]]:
    """Return an import payload and separate question records for one LoCoMo sample."""
    conversation = sample.get("conversation") or {}
    messages = _locomo_messages(conversation)
    questions = [_locomo_question(item) for item in sample.get("qa") or []]
    title = str(sample.get("sample_id") or "LoCoMo conversation")
    return {"title": title, "messages": messages}, questions


def adapt_longmemeval(instance: dict) -> tuple[dict, list[dict]]:
    """Return one haystack as an import payload and one question record."""
    messages: list[dict] = []
    evidence: list[str] = []
    sessions = instance.get("haystack_sessions") or []
    session_ids = instance.get("haystack_session_ids") or []
    dates = instance.get("haystack_dates") or []
    for index, session in enumerate(sessions):
        _append_session(messages, evidence, session, _at(session_ids, index), _at(dates, index))
    question = {
        "id": str(instance.get("question_id") or "question"),
        "category": str(instance.get("question_type") or "unspecified"),
        "question": str(instance.get("question") or ""),
        "answer": instance.get("answer"),
        "evidence_source_ids": evidence,
        "topic_keywords": [],
    }
    title = str(instance.get("question_id") or "LongMemEval haystack")
    return {"title": title, "messages": messages}, [question]


def _locomo_messages(conversation: dict) -> list[dict]:
    messages: list[dict] = []
    index = 1
    while f"session_{index}" in conversation:
        stamp = _parse_time(conversation.get(f"session_{index}_date_time"))
        for turn in conversation[f"session_{index}"]:
            messages.append(_locomo_turn(turn, stamp))
        index += 1
    return messages


def _locomo_turn(turn: dict, stamp: str | None) -> dict:
    return {
        "speaker": str(turn.get("speaker") or "Speaker"),
        "content": str(turn.get("text") or ""),
        "source_id": str(turn.get("dia_id") or ""),
        "timestamp": stamp,
    }


def _locomo_question(item: dict) -> dict:
    return {
        "id": str(item.get("question") or "")[:80],
        "category": str(item.get("category") or ""),
        "question": str(item.get("question") or ""),
        "answer": item.get("answer"),
        "evidence_source_ids": [str(value) for value in item.get("evidence") or []],
        "topic_keywords": [],
    }


def _append_session(messages: list[dict], evidence: list[str], session: list, session_id: str, stamp: str) -> None:
    for index, turn in enumerate(session):
        source_id = f"{session_id}:{index}"
        messages.append(_long_turn(turn, source_id, stamp))
        if turn.get("has_answer") is True:
            evidence.append(source_id)


def _long_turn(turn: dict, source_id: str, stamp: str) -> dict:
    return {
        "speaker": "User" if turn.get("role") == "user" else "Assistant",
        "content": str(turn.get("content") or ""),
        "source_id": source_id,
        "timestamp": _parse_time(stamp),
    }


def _at(values: list, index: int) -> str:
    if index >= len(values):
        return f"session-{index}"
    return str(values[index])


def _parse_time(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = _try_parse(value.strip())
    if parsed is None:
        return None
    normalized = ensure_utc(parsed)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


def _try_parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _slash_time(value)


def _slash_time(value: str) -> datetime | None:
    head = value.split(" (")[0]
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(head, pattern)
        except ValueError:
            continue
    return None
