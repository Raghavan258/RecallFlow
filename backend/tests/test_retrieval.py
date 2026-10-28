"""Retrieval behavior for the synthetic conversation and the API."""

from app.constants import GRAPH_EDGE_BONUS
from app.datasets.synthetic import load_synthetic
from app.retrieval.budget import count_tokens, evidence_block
from app.retrieval.engine import retrieve
from app.retrieval.evaluate import evaluate_questions
from app.retrieval.types import RankedMemory, RetrievalCorpus, RetrievalEdge, RetrievalMemory


def test_keyword_graph_and_budget_on_the_synthetic_set():
    conversation, questions = load_synthetic()
    rows = evaluate_questions(conversation, questions, token_budget=40, limit=5)
    by_key = {(row["mode"], row["question_id"]): row for row in rows}
    greenhouse = by_key[("keyword", "greenhouse-schedule")]
    assert greenhouse["recall_at_5"] == 1.0
    assert "m1" in greenhouse["evidence_source_ids"]
    hop_keyword = by_key[("keyword", "seedling-hop")]["recall_at_5"]
    hop_graph = by_key[("graph", "seedling-hop")]["recall_at_5"]
    assert hop_graph >= hop_keyword
    assert "m1" in by_key[("graph", "seedling-hop")]["evidence_source_ids"]
    assert "m6" in by_key[("graph", "seedling-hop")]["evidence_source_ids"]
    assert "m5" in by_key[("graph", "bakery-update")]["evidence_source_ids"]
    picnic = by_key[("graph", "river-picnic")]
    assert picnic["topic_keyword_contamination"] == 0.0
    assert "m3" not in picnic["evidence_source_ids"]
    for mode in ("keyword", "graph", "budget"):
        assert by_key[(mode, "wifi-password")]["evidence_source_ids"] == []
    budget = by_key[("budget", "greenhouse-schedule")]
    assert budget["selected_tokens"] <= 40


def _memory(memory_id: str, text: str) -> RetrievalMemory:
    return RetrievalMemory(memory_id, text, (), (), (memory_id,), (memory_id,))


def test_graph_mode_is_one_hop_and_keeps_the_best_lexical_match():
    chain = RetrievalCorpus(
        memories=(
            _memory("c", "alpha launch date"),
            _memory("b", "bakery hours stay early"),
            _memory("a", "river picnic on saturday"),
            _memory("z", "kyoto ticket in june"),
        ),
        topics=(),
        edges=(
            RetrievalEdge("SUPPORTS", "c", "b"),
            RetrievalEdge("SUPPORTS", "b", "a"),
            RetrievalEdge("SUPPORTS", "a", "z"),
        ),
    )
    hop = retrieve(chain, "When is the alpha launch?", "graph", limit=5, token_budget=180)
    ids = [item.memory.id for item in hop.evidence]
    assert ids[0] == "c"
    assert "b" in ids
    assert "a" not in ids and "z" not in ids
    seed = next(item for item in hop.evidence if item.memory.id == "c")
    neighbor = next(item for item in hop.evidence if item.memory.id == "b")
    assert seed.score == round(2 / 3, 4)
    assert neighbor.score == GRAPH_EDGE_BONUS
    weak = tuple(_memory(f"w{index}", "alpha note") for index in range(14))
    crowded = RetrievalCorpus(memories=weak + (_memory("best", "alpha launch confirmed"),), topics=(), edges=())
    ranked = retrieve(crowded, "alpha launch", "graph", limit=5, token_budget=180)
    assert ranked.evidence[0].memory.id == "best"


def test_budget_never_exceeds_the_tokenizer_count():
    memory = RetrievalMemory("m", "one two three four", (), (), ("s",), ("s",))
    ranked = [RankedMemory(memory, 1.0, "Shared terms: one.", True)]
    block = evidence_block(ranked[0])
    assert count_tokens(block) == len(block.split())
    from app.retrieval.budget import pack

    selected, used, discarded = pack(ranked, budget=2, enforce=True)
    assert used == 0
    assert discarded == 1
    assert selected[0].selected is False


def test_retrieve_api_returns_sources_and_rejects_a_missing_run(client):
    from app.datasets.synthetic import load_synthetic

    conversation, questions = load_synthetic()
    created = client.post("/api/conversations/import", json=conversation)
    assert created.status_code == 200
    question = {"question": "When is the greenhouse tomato schedule?"}
    missing = client.post(f"/api/conversations/{created.json()['id']}/retrieve", json=question)
    assert missing.status_code == 422
    extracted = client.post(f"/api/conversations/{created.json()['id']}/extract")
    assert extracted.status_code == 200
    response = client.post(
        f"/api/conversations/{created.json()['id']}/retrieve",
        json={"question": questions[0]["question"], "mode": "graph", "token_budget": 180, "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "graph"
    assert body["evidence"]
    assert body["evidence"][0]["sources"]
    assert body["evidence"][0]["sources"][0]["content"]
    assert "m1" in body["evidence"][0]["source_ids"] or any("m1" in item["source_ids"] for item in body["evidence"])
    budget = client.post(
        f"/api/conversations/{created.json()['id']}/retrieve",
        json={"question": questions[0]["question"], "mode": "budget", "token_budget": 12, "limit": 5},
    )
    assert budget.status_code == 200
    assert budget.json()["token_usage"]["selected"] <= 12
    empty = client.post(f"/api/conversations/{created.json()['id']}/retrieve", json={"question": " ", "mode": "keyword"})
    assert empty.status_code == 422
    assert client.post("/api/conversations/missing/retrieve", json={"question": "When?"}).status_code == 404
