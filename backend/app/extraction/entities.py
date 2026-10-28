"""Capitalized entity mentions for the baseline extractor."""

from dataclasses import dataclass

from app.extraction.text_utils import capitalized_mentions, slug
from app.extraction.types import ExtractedEntity, MessageInput

NAME_TYPE = "name"


@dataclass
class _Mention:
    name: str
    message_ids: list[str]


def build_entities(messages: list[MessageInput]) -> list[ExtractedEntity]:
    """Collect distinct mid-sentence capitalized mentions."""
    grouped: dict[str, _Mention] = {}
    for message in messages:
        _collect_message(message, grouped)
    return [_to_entity(mention) for mention in grouped.values()]


def _collect_message(message: MessageInput, grouped: dict[str, _Mention]) -> None:
    for name in capitalized_mentions(message.content):
        key = name.casefold()
        mention = grouped.get(key)
        if mention is None:
            grouped[key] = _Mention(name=name, message_ids=[message.id])
        elif message.id not in mention.message_ids:
            mention.message_ids.append(message.id)


def _to_entity(mention: _Mention) -> ExtractedEntity:
    return ExtractedEntity(
        key=f"entity:{slug(mention.name)}",
        name=mention.name,
        entity_type=NAME_TYPE,
        message_ids=mention.message_ids,
    )
