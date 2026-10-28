"""Benchmark labels are authored, and the metric definitions stay stable."""

import json
from pathlib import Path

from app.datasets.benchmark import BENCHMARK_VERSION, DATA_DIR, load_benchmark
from app.retrieval.benchmark import (
    BENCHMARK_BUDGET,
    BENCHMARK_BUDGETS,
    BENCHMARK_LIMIT,
    BENCHMARK_MODES,
    _first_relevant_rank,
    _recall,
    run_benchmark,
)


def test_benchmark_labels_name_real_messages_and_are_not_retrieval_output():
    conversation, questions = load_benchmark()
    assert conversation["version"] == BENCHMARK_VERSION
    assert 50 <= len(questions) <= 100
    source_ids = {item["source_id"] for item in conversation["messages"]}
    contents = {item["content"] for item in conversation["messages"]}
    splits = {item["split"] for item in questions}
    assert splits == {"dev", "heldout"}
    for question in questions:
        assert question["question"] not in contents
        assert set(question["evidence_source_ids"]) <= source_ids
        if question["category"] == "unanswerable":
            assert question["evidence_source_ids"] == []
        else:
            assert question["evidence_source_ids"]


def test_recall_and_rank_use_authored_source_ids():
    gold = ["b03", "b10"]
    lists = [("b10",), ("b11",), ("b03",)]
    assert _recall(gold, lists, 1) == 0.5
    assert _recall(gold, lists, 5) == 1.0
    assert _recall([], lists, 5) is None
    assert _first_relevant_rank(gold, lists) == 1
    assert _first_relevant_rank(["missing"], lists) is None


def test_benchmark_budget_mode_does_not_exceed_the_tokenizer():
    conversation, questions = load_benchmark()
    report = run_benchmark(conversation, questions)
    for body in report["splits"].values():
        budget = body["modes"]["budget"]
        assert budget["budget_violations"] == 0
        assert budget["sample_count"] == body["question_count"]
        assert set(body["modes"]) == set(BENCHMARK_MODES)
    assert report["limit"] == BENCHMARK_LIMIT
    assert report["token_budget"] == BENCHMARK_BUDGET
    assert report["token_budgets"] == list(BENCHMARK_BUDGETS)
    for body in report["splits"].values():
        for budget, summary in body["budget_sweep"].items():
            scored = summary["modes"]["budget"]
            assert scored["budget_violations"] == 0
            assert scored["mean_selected_tokens"] <= int(budget)


def test_heldout_split_is_not_read_by_retrieval_logic():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "benchmark.py":
            continue
        if "heldout" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_dev_dependency_gain_stays_and_heldout_overall_recall_does_not_move():
    conversation, questions = load_benchmark()
    report = run_benchmark(conversation, questions)
    before = json.loads((DATA_DIR / "benchmark_report_before.json").read_text(encoding="utf-8"))
    dev = report["splits"]["dev"]
    heldout = report["splits"]["heldout"]
    assert dev["by_category"]["graph"]["dependency"]["recall_at_5"] == 1.0
    assert dev["modes"]["graph"]["recall_at_5"] > dev["modes"]["keyword"]["recall_at_5"]
    for mode in ("keyword", "graph", "budget"):
        assert heldout["modes"][mode]["recall_at_5"] == before["splits"]["heldout"]["modes"][mode]["recall_at_5"]
        assert heldout["modes"][mode]["mrr"] == before["splits"]["heldout"]["modes"][mode]["mrr"]
