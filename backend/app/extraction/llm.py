"""Optional OpenAI-compatible extractor. API keys stay in the environment."""

import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.errors import ExtractionError
from app.extraction.types import ExtractionResult, MessageInput

SYSTEM_PROMPT = """You extract a conversation memory graph as JSON.
Return an object with provider set to "llm", a limitations array, and arrays
named topics, memories, entities, and relationships.
Topic keys are unique. Subtopics set parent_key to a root topic key.
Memory kinds are fact, claim, decision, preference, requirement, constraint, or question.
Every memory includes message_ids copied from the input. Do not invent ids or timestamps.
Relationships use only CONTAINS, RELATED_TO, MENTIONS, SUPPORTS, DEPENDS_ON, SUPERSEDES,
CONTRADICTS, and DERIVED_FROM. Omit a relationship when the conversation does not support it.
Decision memories use endpoint type decision. Other memories use memory.
"""


class PostClient(Protocol):
    """Minimal HTTP surface used by the LLM extractor."""

    def post(self, url: str, json: dict, headers: dict[str, str]) -> httpx.Response:
        """Send a JSON request."""


class LlmExtractor:
    """Chat-completions extractor. The key is read from configuration, never from code."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        client: PostClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ExtractionError("LLM_API_KEY is required when EXTRACTION_PROVIDER=llm.", status_code=400)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = client

    def extract(self, messages: list[MessageInput]) -> ExtractionResult:
        """Ask the configured model for structured extraction and parse the JSON."""
        content = self._complete(messages)
        return parse_llm_content(content)

    def _complete(self, messages: list[MessageInput]) -> str:
        response = self._post(_request_body(messages, self._model))
        if response.status_code >= 400:
            raise ExtractionError("The language model provider rejected the extraction request.")
        return _content_from_response(response)


    def _post(self, body: dict) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        url = f"{self._base_url}/chat/completions"
        try:
            if self._client is not None:
                return self._client.post(url, json=body, headers=headers)
            with httpx.Client(timeout=self._timeout) as client:
                return client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ExtractionError("The language model provider could not be reached.") from exc


def parse_llm_content(content: str) -> ExtractionResult:
    """Parse a model message into an extraction result."""
    try:
        payload = json.loads(_strip_fences(content))
        result = ExtractionResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ExtractionError("The language model returned extraction JSON that failed validation.") from exc
    return result.model_copy(update={"provider": "llm"})


def _request_body(messages: list[MessageInput], model: str) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _conversation_text(messages)},
        ],
    }


def _conversation_text(messages: list[MessageInput]) -> str:
    lines = [f"[{message.id}] {message.speaker}: {message.content}" for message in messages]
    return "\n".join(lines)


def _strip_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.removesuffix("```").strip()
    return text


def _content_from_response(response: httpx.Response) -> str:
    try:
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ExtractionError("The language model response did not include extraction JSON.") from exc
