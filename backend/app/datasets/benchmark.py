"""Load the versioned benchmark. Questions stay out of the import payload."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
BENCHMARK_VERSION = "benchmark-v1"


def load_benchmark() -> tuple[dict, list[dict]]:
    """Return the studio conversation and the authored questions."""
    conversation = json.loads((DATA_DIR / "benchmark_conversation.json").read_text(encoding="utf-8"))
    evaluation = json.loads((DATA_DIR / "benchmark_questions.json").read_text(encoding="utf-8"))
    return conversation, list(evaluation["questions"])
