"""Choose the extraction provider from settings."""

from app.config import Settings
from app.errors import ExtractionError
from app.extraction.baseline import BaselineExtractor
from app.extraction.llm import LlmExtractor


def build_provider(settings: Settings) -> BaselineExtractor | LlmExtractor:
    """Return the configured extractor. Baseline is the offline default."""
    name = settings.extraction_provider.strip().lower()
    if name == "baseline":
        return BaselineExtractor()
    if name == "llm":
        return LlmExtractor(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    raise ExtractionError(
        "Unknown EXTRACTION_PROVIDER. Use baseline or llm.",
        status_code=400,
    )
