"""Compare unconstrained rankings with fixed-budget packing on the same questions."""

from time import perf_counter

from app.constants import DEFAULT_RETRIEVAL_LIMIT, DEFAULT_TOKEN_BUDGET
from app.extraction.baseline import BaselineExtractor
from app.extraction.types import MessageInput
from app.retrieval.budget import pack
from app.retrieval.corpus import corpus_from_result
from app.retrieval.engine import retrieve
from app.retrieval.types import RetrievalCorpus, RetrievalPack

# keyword and graph do not discard. The budgeted labels use the same whole-memory packer.
# keyword_budget and graph_budget are evaluation labels. The API mode remains `budget`.
MODE_LABELS = (
    ("keyword", "unconstrained"),
    ("graph", "unconstrained"),
    ("keyword_budget", "fixed_budget"),
    ("graph_budget", "fixed_budget"),
    ("budget", "fixed_budget"),
)
EVAL_TOKEN_BUDGETS = (20, 40, 80)


def evaluate_questions(
    conversation: dict,
    questions: list[dict],
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
    include: str = "all",
) -> list[dict]:
    """Score labeled modes on every question. Answers are not passed to retrieval."""
    corpus = _corpus(conversation)
    stored = _stored_source_ids(corpus)
    rows: list[dict] = []
    for mode, constraint in _labels(include):
        rows.extend(_mode_rows(corpus, stored, questions, mode, constraint, token_budget, limit))
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    """Average metrics by mode, constraint, budget, and category."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["mode"], row["constraint"], row["token_budget"], row["category"])
        groups.setdefault(key, []).append(row)
    return [_average(*key, items) for key, items in sorted(groups.items(), key=_group_sort)]


def _labels(include: str) -> tuple[tuple[str, str], ...]:
    if include == "all":
        return MODE_LABELS
    return tuple(item for item in MODE_LABELS if include in item)


def _group_sort(item: tuple[tuple, list]) -> tuple:
    mode, constraint, budget, category = item[0]
    return (constraint, budget if budget is not None else -1, mode, category)


def _corpus(conversation: dict) -> RetrievalCorpus:
    messages = [
        MessageInput(
            id=item.get("source_id") or f"m{index}",
            speaker=item["speaker"],
            content=item["content"],
            position=index,
            source_id=item.get("source_id"),
        )
        for index, item in enumerate(conversation["messages"])
    ]
    return corpus_from_result(messages, BaselineExtractor().extract(messages))


def _stored_source_ids(corpus: RetrievalCorpus) -> set[str]:
    return {source_id for memory in corpus.memories for source_id in memory.source_ids}


def _mode_rows(
    corpus: RetrievalCorpus,
    stored: set[str],
    questions: list[dict],
    mode: str,
    constraint: str,
    token_budget: int,
    limit: int,
) -> list[dict]:
    rows: list[dict] = []
    for question in questions:
        started = perf_counter()
        result = _retrieve(corpus, question["question"], mode, token_budget, limit)
        latency_ms = (perf_counter() - started) * 1000
        rows.append(_row(question, mode, constraint, result, stored, latency_ms))
    return rows


def _retrieve(corpus: RetrievalCorpus, question: str, mode: str, token_budget: int, limit: int) -> RetrievalPack:
    if mode in {"keyword_budget", "graph_budget"}:
        ranked = retrieve(corpus, question, mode.split("_")[0], limit=limit, token_budget=token_budget)
        return _enforce(ranked, token_budget, mode)
    return retrieve(corpus, question, mode, limit=limit, token_budget=token_budget)


def _enforce(result: RetrievalPack, token_budget: int, mode: str) -> RetrievalPack:
    selected, used, discarded = pack(list(result.evidence), token_budget, enforce=True)
    return RetrievalPack(
        mode=mode,
        evidence=tuple(selected),
        token_budget=token_budget,
        selected_tokens=used,
        discarded=discarded,
    )


def _row(
    question: dict,
    mode: str,
    constraint: str,
    result: RetrievalPack,
    stored: set[str],
    latency_ms: float,
) -> dict:
    selected = [item for item in result.evidence if item.selected]
    found = {source_id for item in selected for source_id in item.memory.source_ids}
    gold = list(question["evidence_source_ids"])
    return {
        "mode": mode,
        "constraint": constraint,
        "token_budget": result.token_budget if constraint == "fixed_budget" else None,
        "category": question["category"],
        "question_id": question["id"],
        "recall_at_5": _recall(gold, found),
        "conditional_recall_at_5": _conditional_recall(gold, found, stored),
        "extraction_coverage": _coverage(gold, stored),
        "topic_keyword_contamination": _topic_keyword_contamination(selected, question["topic_keywords"]),
        "false_retrieval_rate": _false_retrieval_rate(selected, gold),
        "selected_tokens": result.selected_tokens,
        "discarded": result.discarded,
        "latency_ms": round(latency_ms, 3),
        "evidence_source_ids": sorted(found),
    }


def _recall(gold: list[str], found: set[str]) -> float | None:
    """Fraction of gold source ids present on the selected memories. Empty gold is undefined."""
    if not gold:
        return None
    return len(set(gold) & found) / len(set(gold))


def _coverage(gold: list[str], stored: set[str]) -> float | None:
    """Fraction of gold source ids that the extractor stored on any memory."""
    if not gold:
        return None
    return len(set(gold) & stored) / len(set(gold))


def _conditional_recall(gold: list[str], found: set[str], stored: set[str]) -> float | None:
    """Recall among gold source ids the extractor actually stored."""
    available = set(gold) & stored
    if not available:
        return None
    return len(available & found) / len(available)


def _topic_keyword_contamination(selected, keywords: list[str]) -> float:
    """Share of selected memories whose topic labels miss every labeled keyword.

    This is a topic-keyword heuristic, not a judgment that the memory is irrelevant.
    """
    if not selected:
        return 0.0
    missed = [item for item in selected if not _label_has_keyword(item.memory.topic_labels, keywords)]
    return len(missed) / len(selected)


def _label_has_keyword(labels: tuple[str, ...], keywords: list[str]) -> bool:
    if not keywords:
        return False
    blob = " ".join(labels).lower()
    return any(keyword.lower() in blob for keyword in keywords)


def _false_retrieval_rate(selected, gold: list[str]) -> float:
    """Share of selected memories that carry none of the gold source ids."""
    if not selected:
        return 0.0
    gold_ids = set(gold)
    missed = [item for item in selected if not set(item.memory.source_ids) & gold_ids]
    return len(missed) / len(selected)


def _average(mode: str, constraint: str, token_budget: int | None, category: str, items: list[dict]) -> dict:
    return {
        "mode": mode,
        "constraint": constraint,
        "token_budget": token_budget,
        "category": category,
        "sample_size": len(items),
        "recall_at_5": _mean(_defined(items, "recall_at_5")),
        "conditional_recall_at_5": _mean(_defined(items, "conditional_recall_at_5")),
        "extraction_coverage": _mean(_defined(items, "extraction_coverage")),
        "topic_keyword_contamination": _mean([item["topic_keyword_contamination"] for item in items]),
        "false_retrieval_rate": _mean([item["false_retrieval_rate"] for item in items]),
        "selected_tokens": _mean([item["selected_tokens"] for item in items]),
        "latency_ms": _mean([item["latency_ms"] for item in items]),
    }


def _defined(items: list[dict], key: str) -> list[float]:
    return [item[key] for item in items if item[key] is not None]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def main() -> None:
    """Print unconstrained baselines, then the fixed-budget sweep. No external model."""
    from app.datasets.synthetic import load_synthetic

    conversation, questions = load_synthetic()
    _print_section("unconstrained", evaluate_questions(conversation, questions, include="unconstrained"))
    for budget in EVAL_TOKEN_BUDGETS:
        rows = evaluate_questions(conversation, questions, token_budget=budget, include="fixed_budget")
        _print_section(f"fixed_budget {budget}", rows)


def _print_section(title: str, rows: list[dict]) -> None:
    print(title)
    for row in summarize(rows):
        print(row)


if __name__ == "__main__":
    main()
