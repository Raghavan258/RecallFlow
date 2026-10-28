"""Score keyword, graph, and budget retrieval on the authored benchmark.

Recall and MRR use answerable questions only. An answerable question has at least
one authored source id. Unanswerable questions are reported through the empty-result
rate and are not placed in the recall or MRR denominators.
"""

import json
from time import perf_counter

from app.extraction.text_utils import tokens
from app.retrieval.budget import count_tokens, evidence_block
from app.retrieval.engine import retrieve
from app.retrieval.evaluate import _corpus
from app.retrieval.lexical import query_terms
from app.retrieval.types import RetrievalPack

BENCHMARK_LIMIT = 10
BENCHMARK_BUDGET = 80
BENCHMARK_BUDGETS = (20, 40, 80)
BENCHMARK_MODES = ("keyword", "graph", "budget")
REPORT_PATH_NAME = "benchmark_report.json"


def run_benchmark(conversation: dict, questions: list[dict]) -> dict:
    """Score every split and mode. The question text is the only retrieval input.

    The dev and held-out labels group the report. They are not passed to retrieval.
    """
    corpus = _corpus(conversation)
    memory_index = _memory_index(corpus)
    return {
        "version": conversation.get("version"),
        "limit": BENCHMARK_LIMIT,
        "token_budget": BENCHMARK_BUDGET,
        "token_budgets": list(BENCHMARK_BUDGETS),
        "tokenizer": "whitespace split of the memory text plus the Sources line",
        "latency_method": "one time.perf_counter interval around retrieve, in milliseconds",
        "memory_index": memory_index,
        "paraphrase_overlap": _paraphrase_overlap(conversation, questions),
        "splits": {
            split: _split_report(corpus, _for_split(questions, split))
            for split in ("dev", "heldout")
        },
    }


def write_report(report: dict, path) -> None:
    """Write the machine-readable report."""
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _budget_sweep(corpus, questions: list[dict]) -> dict[str, dict]:
    """Score budget mode at each fixed budget. Ranking settings stay the same."""
    return {str(budget): _budget_summary(corpus, questions, budget) for budget in BENCHMARK_BUDGETS}


def _budget_summary(corpus, questions: list[dict], budget: int) -> dict:
    rows = [_budget_row(corpus, question, budget) for question in questions]
    return {"modes": {"budget": _summarize(rows, "budget")}, "by_category": _by_category(rows, "budget")}


def _budget_row(corpus, question: dict, budget: int) -> dict:
    gold = list(question["evidence_source_ids"])
    started = perf_counter()
    pack = retrieve(corpus, question["question"], "budget", limit=BENCHMARK_LIMIT, token_budget=budget)
    latency_ms = (perf_counter() - started) * 1000
    return {"category": question["category"], "modes": {"budget": _mode_score(pack, gold, latency_ms)}}


def _paraphrase_overlap(conversation: dict, questions: list[dict]) -> list[dict]:
    """Record content-token overlap. This does not change retrieval."""
    text_of = {item["source_id"]: item["content"] for item in conversation["messages"]}
    return [_overlap_row(question, text_of) for question in questions if question["category"] == "paraphrase"]


def _overlap_row(question: dict, text_of: dict[str, str]) -> dict:
    query = query_terms(question["question"])
    gold_text = " ".join(text_of[source_id] for source_id in question["evidence_source_ids"])
    gold_terms = set(tokens(gold_text))
    shared = [term for term in query if term in gold_terms]
    return {
        "id": question["id"],
        "split": question["split"],
        "query_terms": list(query),
        "shared_with_gold": shared,
    }


def _for_split(questions: list[dict], split: str) -> list[dict]:
    return [item for item in questions if item["split"] == split]


def _memory_index(corpus) -> dict[str, list[str]]:
    """Map a source id to extractor memory keys. Rank order is not used."""
    found: dict[str, list[str]] = {}
    for memory in corpus.memories:
        for source_id in memory.source_ids:
            found.setdefault(source_id, []).append(memory.id)
    return {source_id: ids for source_id, ids in sorted(found.items())}


def _split_report(corpus, questions: list[dict]) -> dict:
    rows = [_score_question(corpus, question) for question in questions]
    return {
        "question_count": len(questions),
        "answerable_count": sum(1 for question in questions if question["evidence_source_ids"]),
        "unanswerable_count": sum(1 for question in questions if not question["evidence_source_ids"]),
        "modes": {mode: _summarize(rows, mode) for mode in BENCHMARK_MODES},
        "by_category": {mode: _by_category(rows, mode) for mode in BENCHMARK_MODES},
        "budget_sweep": _budget_sweep(corpus, questions),
        "questions": rows,
    }


def _score_question(corpus, question: dict) -> dict:
    gold = list(question["evidence_source_ids"])
    modes = {}
    for mode in BENCHMARK_MODES:
        started = perf_counter()
        pack = retrieve(corpus, question["question"], mode, limit=BENCHMARK_LIMIT, token_budget=BENCHMARK_BUDGET)
        latency_ms = (perf_counter() - started) * 1000
        modes[mode] = _mode_score(pack, gold, latency_ms)
    return {"id": question["id"], "split": question["split"], "category": question["category"], "modes": modes}


def _mode_score(pack: RetrievalPack, gold: list[str], latency_ms: float) -> dict:
    selected = [item for item in pack.evidence if item.selected]
    lists = [item.memory.source_ids for item in selected]
    rank = _first_relevant_rank(gold, lists)
    tokens = _selected_tokens(selected)
    return {
        "recall_at_1": _recall(gold, lists, 1),
        "recall_at_5": _recall(gold, lists, 5),
        "recall_at_10": _recall(gold, lists, 10),
        "reciprocal_rank": None if not gold else (0.0 if rank is None else round(1 / rank, 4)),
        "first_relevant_rank": rank,
        "selected_count": len(selected),
        "selected_tokens": tokens,
        "budget_violation": bool(pack.mode == "budget" and tokens > pack.token_budget),
        "empty": not selected,
        "latency_ms": round(latency_ms, 3),
        "evidence_source_ids": _ordered_sources(lists),
    }


def _selected_tokens(selected) -> int:
    return sum(count_tokens(evidence_block(item)) for item in selected)


def _ordered_sources(lists: list[tuple[str, ...]]) -> list[str]:
    found: list[str] = []
    for sources in lists:
        for source_id in sources:
            if source_id not in found:
                found.append(source_id)
    return found


def _recall(gold: list[str], lists: list[tuple[str, ...]], cutoff: int) -> float | None:
    """Fraction of authored source ids present in the first `cutoff` selected memories."""
    if not gold:
        return None
    found: set[str] = set()
    for sources in lists[:cutoff]:
        found.update(sources)
    return round(len(set(gold) & found) / len(set(gold)), 4)


def _first_relevant_rank(gold: list[str], lists: list[tuple[str, ...]]) -> int | None:
    """1-based rank of the first selected memory that carries an authored source id."""
    if not gold:
        return None
    needed = set(gold)
    for index, sources in enumerate(lists, start=1):
        if needed & set(sources):
            return index
    return None


def _summarize(rows: list[dict], mode: str) -> dict:
    scored = [row["modes"][mode] for row in rows]
    answerable = [item for item, row in zip(scored, rows) if row["modes"][mode]["recall_at_5"] is not None]
    unanswerable = [item for item in scored if item["recall_at_5"] is None]
    return {
        "sample_count": len(scored),
        "answerable_denominator": len(answerable),
        "unanswerable_denominator": len(unanswerable),
        "recall_at_1": _mean([item["recall_at_1"] for item in answerable]),
        "recall_at_5": _mean([item["recall_at_5"] for item in answerable]),
        "recall_at_10": _mean([item["recall_at_10"] for item in answerable]),
        "mrr": _mean([item["reciprocal_rank"] for item in answerable]),
        "mean_selected_tokens": _mean([item["selected_tokens"] for item in scored]),
        "budget_violations": sum(1 for item in scored if item["budget_violation"]),
        "empty_result_rate_answerable": _rate(answerable, True),
        "empty_result_rate_unanswerable": _rate(unanswerable, True),
        "mean_latency_ms": _mean([item["latency_ms"] for item in scored]),
    }


def _rate(items: list[dict], empty: bool) -> float | None:
    if not items:
        return None
    matched = sum(1 for item in items if item["empty"] is empty)
    return round(matched / len(items), 4)


def _mean(values: list[float | None]) -> float | None:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


def main() -> None:
    """Write benchmark_report.json next to the dataset. No external model is called."""
    from app.datasets.benchmark import load_benchmark

    conversation, questions = load_benchmark()
    report = run_benchmark(conversation, questions)
    path = conversation_path(REPORT_PATH_NAME)
    write_report(report, path)
    _print_summary(report)


def _print_summary(report: dict) -> None:
    for split, body in report["splits"].items():
        print(split, body["question_count"], "answerable", body["answerable_count"])
        for mode, summary in body["modes"].items():
            print(mode, _brief(summary))
        for budget, summary in body["budget_sweep"].items():
            print("budget", budget, _brief(summary["modes"]["budget"]))


def _brief(summary: dict) -> dict:
    keys = (
        "recall_at_1",
        "recall_at_5",
        "recall_at_10",
        "mrr",
        "mean_selected_tokens",
        "budget_violations",
        "empty_result_rate_unanswerable",
        "empty_result_rate_answerable",
        "mean_latency_ms",
        "sample_count",
    )
    return {key: summary[key] for key in keys}


def conversation_path(name: str):
    from app.datasets.benchmark import DATA_DIR

    return DATA_DIR / name


def _by_category(rows: list[dict], mode: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    return {category: _summarize(items, mode) for category, items in sorted(groups.items())}


if __name__ == "__main__":
    main()
