"""Load the committed synthetic conversation and its separate evaluation file."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_synthetic() -> tuple[dict, list[dict]]:
    """Return the import payload and the questions. Questions are not part of the import."""
    conversation = json.loads((DATA_DIR / "synthetic_conversation.json").read_text(encoding="utf-8"))
    evaluation = json.loads((DATA_DIR / "synthetic_eval.json").read_text(encoding="utf-8"))
    return conversation, list(evaluation["questions"])
