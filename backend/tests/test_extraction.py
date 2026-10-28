"""Direct coverage for validation and the optional model parser."""

import pytest

from app.errors import ExtractionError
from app.extraction.llm import LlmExtractor, parse_llm_content
from app.extraction.types import ExtractedRelationship, ExtractionResult
from app.extraction.validate import validate_extraction


def test_validation_rejects_unknown_message_and_duplicate_topic():
    result = ExtractionResult(
        provider="baseline",
        limitations=[],
        topics=[
            {"key": "topic:a", "label": "A", "keywords": ["a"], "summary": "A"},
            {"key": "topic:a", "label": "A again", "keywords": ["a"], "summary": "A"},
        ],
        memories=[],
        entities=[],
        relationships=[],
    )
    with pytest.raises(ExtractionError):
        validate_extraction(result, set())


def test_validation_rejects_dangling_relationship():
    result = ExtractionResult(
        provider="baseline",
        limitations=[],
        topics=[{"key": "topic:a", "label": "A", "keywords": ["a"], "summary": "Repeated terms."}],
        memories=[],
        entities=[],
        relationships=[
            ExtractedRelationship(
                relation_type="CONTAINS",
                source_type="topic",
                source_key="topic:missing",
                target_type="topic",
                target_key="topic:a",
            )
        ],
    )
    with pytest.raises(ExtractionError):
        validate_extraction(result, set())


def test_llm_parser_strips_fences_and_missing_key_is_clear():
    payload = """```json
    {"provider":"llm","limitations":["model"],"topics":[],"memories":[],"entities":[],"relationships":[]}
    ```"""
    parsed = parse_llm_content(payload)
    assert parsed.provider == "llm"
    with pytest.raises(ExtractionError, match="LLM_API_KEY"):
        LlmExtractor(api_key="  ", base_url="https://example.invalid", model="test", timeout=1)
    with pytest.raises(ExtractionError):
        parse_llm_content("not json")
