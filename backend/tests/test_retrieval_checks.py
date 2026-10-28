"""Packing, graph ranking, and fixed-budget evaluation checks."""

import pytest

from app.constants import CORRECTION_SOURCE_BONUS
from app.datasets.synthetic import load_synthetic
from app.retrieval.budget import count_tokens, evidence_block, pack
from app.retrieval.engine import retrieve
from app.retrieval.evaluate import EVAL_TOKEN_BUDGETS, evaluate_questions
from app.retrieval.types import RankedMemory, RetrievalCorpus, RetrievalEdge, RetrievalMemory


def _memory(memory_id: str, text: str, source: str | None = None) -> RetrievalMemory:
    label = source or memory_id
    return RetrievalMemory(memory_id, text, (), (), (label,), (label,))


def _tagged(memory_id: str, text: str, topic: str) -> RetrievalMemory:
    return RetrievalMemory(memory_id, text, (topic,), (topic,), (memory_id,), (memory_id,))


def _ranked(memory: RetrievalMemory, score: float) -> RankedMemory:
    return RankedMemory(memory, score, "rank", True)


def test_packer_skips_a_large_item_and_keeps_a_later_one():
    large = _ranked(_memory("large", "one two three four five"), 1.0)
    small = _ranked(_memory("small", "one"), 0.2)
    selected, used, discarded = pack([large, small], budget=3, enforce=True)
    assert selected[0].selected is False
    assert selected[1].selected is True
    assert discarded == 1
    assert used == count_tokens(evidence_block(small))
    assert used <= 3


def test_packer_discards_everything_when_nothing_fits():
    items = [_ranked(_memory("a", "one two three"), 1.0), _ranked(_memory("b", "four five six"), 0.5)]
    selected, used, discarded = pack(items, budget=0, enforce=True)
    assert used == 0
    assert discarded == 2
    assert all(item.selected is False for item in selected)


def test_negative_budget_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        pack([_ranked(_memory("a", "one"), 1.0)], budget=-1, enforce=True)


def test_token_count_includes_source_identifiers():
    short = _ranked(RetrievalMemory("m", "one", (), (), ("m",), ("aa",)), 1.0)
    longer = _ranked(RetrievalMemory("m", "one", (), (), ("m",), ("aa", "bbbb")), 1.0)
    assert "aa" in evidence_block(short)
    assert count_tokens(evidence_block(longer)) > count_tokens(evidence_block(short))


def test_limit_does_not_backfill_past_the_candidate_window():
    question = "alpha launch"
    memories = (
        _memory("m", "alpha launch " + " ".join(f"word{index}" for index in range(30))),
        _memory("a", "alpha"),
        _memory("b", "alpha"),
    )
    pack_result = retrieve(RetrievalCorpus(memories, (), ()), question, "budget", limit=1, token_budget=2)
    assert [item.memory.id for item in pack_result.evidence] == ["m"]
    assert pack_result.selected_tokens == 0
    assert pack_result.discarded == 1


def test_depends_on_follows_only_the_needed_topic():
    seed = _tagged("s", "seedling delivery window", "seedling")
    needed = _tagged("g", "monday greenhouse tomato schedule", "greenhouse")
    decoy = _tagged("b", "bakery opening hour", "bakery")
    question = "When is the seedling delivery?"
    forward = RetrievalEdge("DEPENDS_ON", "seedling", "greenhouse")
    reverse = RetrievalEdge("DEPENDS_ON", "greenhouse", "seedling")
    found = _ids(_graph((seed, needed, decoy), (forward,), question))
    assert "g" in found and "b" not in found
    assert "g" not in _ids(_graph((seed, needed, decoy), (reverse,), question))


def test_correction_bonus_requires_both_endpoints():
    question = "What is the bakery opening hour?"
    old = _memory("old", "bakery opening hour is eight")
    new = _memory("new", "bakery opening hour is seven")
    both = _graph((old, new), (RetrievalEdge("SUPERSEDES", "new", "old"),), question)
    scores = {item.memory.id: item.score for item in both.evidence}
    assert scores["new"] == round(scores["old"] + CORRECTION_SOURCE_BONUS, 4)
    alone = _graph((new,), (RetrievalEdge("SUPERSEDES", "new", "missing"),), question)
    assert alone.evidence[0].score == scores["old"]
    contradicted = _graph((old, new), (RetrievalEdge("CONTRADICTS", "new", "old"),), question)
    contradicted_scores = {item.memory.id: item.score for item in contradicted.evidence}
    assert contradicted_scores["new"] == scores["new"]
    assert contradicted_scores["old"] == scores["old"]


def test_graph_explanations_name_terms_and_correction_direction():
    old = _memory("old", "bakery opening hour is eight")
    new = _memory("new", "bakery opening hour is seven")
    result = _graph((old, new), (RetrievalEdge("SUPERSEDES", "new", "old"),), "What is the bakery opening hour?")
    by_id = {item.memory.id: item for item in result.evidence}
    assert by_id["new"].explanation.startswith("Shared terms: bakery, opening, hour.")
    assert "Supersedes old." in by_id["new"].explanation
    assert "Superseded by new." in by_id["old"].explanation
    assert new.text not in by_id["new"].explanation
    neighbor = _graph(
        (_memory("c", "alpha launch date"), _memory("b", "bakery hours stay early")),
        (RetrievalEdge("SUPPORTS", "c", "b"),),
        "When is the alpha launch?",
    )
    reasons = {item.memory.id: item.explanation for item in neighbor.evidence}
    assert reasons["c"].startswith("Shared terms:")
    assert reasons["b"] == "Included through a stored SUPPORTS link."


def test_graph_follows_a_depends_on_phrase_without_a_stored_edge():
    seed = _memory("need", "The glaze recipe depends on the kiln firing temperature.")
    fact = _memory("heat", "The kiln firing temperature is 1000 degrees.")
    other = _memory("fee", "The membership fee is 30 dollars for community access.")
    corpus = RetrievalCorpus((seed, fact, other), (), ())
    graph = retrieve(corpus, "What does the glaze recipe depend on?", "graph", limit=5, token_budget=180)
    keyword = retrieve(corpus, "What does the glaze recipe depend on?", "keyword", limit=5, token_budget=180)
    assert "heat" in _ids(graph)
    assert "heat" not in _ids(keyword)
    assert "fee" not in _ids(graph)


def test_equal_scores_break_ties_by_memory_id():
    corpus = RetrievalCorpus((_memory("b", "alpha launch date"), _memory("a", "alpha launch date")), (), ())
    result = retrieve(corpus, "When is the alpha launch?", "keyword", limit=5, token_budget=180)
    assert [item.memory.id for item in result.evidence] == ["a", "b"]
    assert result.evidence[0].score == result.evidence[1].score


def test_fixed_budget_labels_use_one_packer_and_respect_the_budget():
    conversation, questions = load_synthetic()
    for budget in (0, *EVAL_TOKEN_BUDGETS):
        rows = evaluate_questions(conversation, questions, token_budget=budget)
        by_key = {(row["mode"], row["question_id"]): row for row in rows}
        for row in rows:
            if row["constraint"] == "fixed_budget":
                assert row["token_budget"] == budget
                assert row["selected_tokens"] <= budget
            else:
                assert row["token_budget"] is None
                assert row["discarded"] == 0
        for question in questions:
            packed = by_key[("graph_budget", question["id"])]
            api_mode = by_key[("budget", question["id"])]
            assert packed["evidence_source_ids"] == api_mode["evidence_source_ids"]
            assert packed["selected_tokens"] == api_mode["selected_tokens"]


def test_metrics_separate_coverage_false_hits_and_unanswerable_questions():
    conversation, questions = load_synthetic()
    rows = evaluate_questions(conversation, questions, token_budget=40)
    by_key = {(row["mode"], row["question_id"]): row for row in rows}
    for mode in ("keyword", "graph", "budget", "keyword_budget", "graph_budget"):
        assert by_key[(mode, "wifi-password")]["evidence_source_ids"] == []
        assert by_key[(mode, "wifi-password")]["recall_at_5"] is None
        assert by_key[(mode, "printer-owner")]["false_retrieval_rate"] == 0.0
        assert by_key[(mode, "printer-owner")]["evidence_source_ids"] == []
    missing = {
        "id": "missing-evidence",
        "category": "single_topic",
        "question": "When is the greenhouse tomato schedule?",
        "evidence_source_ids": ["m1", "not-a-message"],
        "topic_keywords": ["greenhouse"],
    }
    row = evaluate_questions(conversation, [missing], token_budget=40, include="keyword")[0]
    assert row["extraction_coverage"] == 0.5
    assert row["conditional_recall_at_5"] == 1.0
    assert row["recall_at_5"] == 0.5
    _assert_false_hit()


def test_each_synthetic_category_has_multiple_questions():
    _, questions = load_synthetic()
    counts: dict[str, int] = {}
    for question in questions:
        counts[question["category"]] = counts.get(question["category"], 0) + 1
    for category in ("single_topic", "temporal_update", "multi_hop", "distractor", "unanswerable"):
        assert counts[category] >= 2


def test_retrieve_api_rejects_a_negative_budget(client):
    response = client.post(
        "/api/conversations/missing/retrieve",
        json={"question": "When?", "mode": "budget", "token_budget": -1},
    )
    assert response.status_code == 422


def _graph(memories: tuple[RetrievalMemory, ...], edges: tuple[RetrievalEdge, ...], question: str):
    corpus = RetrievalCorpus(memories, (), edges)
    return retrieve(corpus, question, "graph", limit=5, token_budget=400)


def _ids(result) -> set[str]:
    return {item.memory.id for item in result.evidence}


def _assert_false_hit() -> None:
    conversation = {
        "title": "False hit",
        "messages": [
            {"speaker": "Ava", "source_id": "p1", "content": "The office wifi password is posted on the router."},
            {"speaker": "Ben", "source_id": "p2", "content": "The office wifi password is posted on the router today."},
        ],
    }
    questions = [
        {
            "id": "false-wifi",
            "category": "unanswerable",
            "question": "What is the office wifi password?",
            "evidence_source_ids": [],
            "topic_keywords": [],
        }
    ]
    row = evaluate_questions(conversation, questions, token_budget=180, include="keyword")[0]
    assert row["evidence_source_ids"]
    assert row["false_retrieval_rate"] == 1.0
    assert row["recall_at_5"] is None
