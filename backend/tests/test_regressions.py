"""Regression checks for corrections, boundaries, timestamps, and re-extraction."""

from app.extraction.baseline import BaselineExtractor
from app.extraction.relations import build_relationships
from app.extraction.text_utils import phrase_in_text
from app.extraction.types import ExtractedEntity, ExtractedMemory, MessageInput
from app.graph.builder import EntityView, GraphRecords, MemoryView, build_graph


def test_topicless_sentence_does_not_inherit_topics():
    messages = [
        MessageInput(id="m1", speaker="Ava", content="Onboarding must stay short for new teams.", position=0),
        MessageInput(
            id="m2",
            speaker="Ben",
            content="Onboarding must stay short for new teams. Lunch is at noon today.",
            position=1,
        ),
    ]
    result = BaselineExtractor().extract(messages)
    lunch = next(item for item in result.memories if item.text.startswith("Lunch"))
    assert lunch.topic_keys == []
    supports = [item for item in result.relationships if item.relation_type == "SUPPORTS" and item.source_key == lunch.key]
    assert supports == []


def test_correction_edges_use_exact_memory_ids(client):
    created = client.post("/api/conversations/import", json=_correction_payload()).json()
    graph = client.post(f"/api/conversations/{created['id']}/extract").json()
    may = _memory_id(graph, "The launch timeline is May.")
    april = _memory_id(graph, "Actually the launch timeline is April.")
    supersede = _memory_id(graph, "This supersedes the May launch timeline.")
    budget = _memory_id(graph, "The launch budget is fixed.")
    june = _memory_id(graph, "Actually the launch date moved to June.")
    contradicts = _pairs(graph, "CONTRADICTS")
    supersedes = _pairs(graph, "SUPERSEDES")
    assert {"source": april, "target": may} in contradicts
    assert {"source": supersede, "target": may} in supersedes
    may_message = created["messages"][0]["id"]
    later_message = created["messages"][1]["id"]
    contradicting = next(edge for edge in graph["edges"] if edge["type"] == "CONTRADICTS" and edge["source"] == april)
    assert contradicting["evidence_message_ids"] == [later_message, may_message]
    linked = {item for pair in contradicts + supersedes for item in pair.values()}
    assert budget not in linked
    assert june not in linked
    assert {may, april, supersede, budget, june} <= {node["id"] for node in graph["nodes"]}


def test_other_correction_cues_need_two_shared_tokens():
    messages = [
        MessageInput(id="m1", speaker="Ava", content="The launch timeline is May.", position=0),
        MessageInput(id="m2", speaker="Ben", content="The launch timeline no longer is May.", position=1),
        MessageInput(
            id="m3",
            speaker="Cleo",
            content="The April launch timeline contradicts the May launch timeline.",
            position=2,
        ),
    ]
    result = BaselineExtractor().extract(messages)
    by_text = {item.text: item.key for item in result.memories}
    pairs = {(item.source_key, item.target_key) for item in result.relationships if item.relation_type == "CONTRADICTS"}
    may = by_text["The launch timeline is May."]
    longer = by_text["The launch timeline no longer is May."]
    contradicts = by_text["The April launch timeline contradicts the May launch timeline."]
    assert (longer, may) in pairs
    assert (contradicts, may) in pairs or (contradicts, longer) in pairs


def test_tim_is_not_matched_inside_timeline():
    memory = ExtractedMemory(
        key="mem",
        kind="fact",
        text="The timeline is May.",
        topic_keys=["launch"],
        message_ids=["m1"],
    )
    entity = ExtractedEntity(key="tim", name="Tim", entity_type="person", message_ids=["m1"])
    relations = build_relationships([], [memory], [entity])
    assert [item for item in relations if item.relation_type == "MENTIONS"] == []
    nodes, _edges = build_graph(
        GraphRecords(
            topics=(),
            memories=(
                MemoryView(
                    id="mem",
                    kind="fact",
                    text="The timeline is May.",
                    topic_ids=("topic-launch",),
                    message_ids=("m1",),
                    confidence=0.45,
                ),
            ),
            entities=(EntityView(id="tim", name="Tim", entity_type="person", message_ids=("m1",)),),
            messages=(),
            relationships=(),
        )
    )
    tim = next(node for node in nodes if node.id == "tim")
    assert tim.topic_ids == []


def test_standalone_tim_is_mentioned():
    memory = ExtractedMemory(key="mem", kind="fact", text="I asked Tim about the date.", topic_keys=[], message_ids=["m1"])
    entity = ExtractedEntity(key="tim", name="Tim", entity_type="person", message_ids=["m1"])
    mentions = [item for item in build_relationships([], [memory], [entity]) if item.relation_type == "MENTIONS"]
    assert len(mentions) == 1
    assert mentions[0].source_key == "mem"
    assert mentions[0].target_key == "tim"


def test_timestamps_round_trip_as_utc(client):
    response = client.post(
        "/api/conversations/import",
        json={
            "title": "Times",
            "messages": [
                {"speaker": "Ava", "content": "UTC note", "timestamp": "2026-03-02T15:00:00Z"},
                {"speaker": "Ben", "content": "Offset note", "timestamp": "2026-03-02T15:00:00+05:30"},
                {"speaker": "Cleo", "content": "Missing note"},
            ],
        },
    )
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert messages[0]["timestamp"] == "2026-03-02T15:00:00Z"
    assert messages[1]["timestamp"] == "2026-03-02T09:30:00Z"
    assert messages[2]["timestamp"] is None
    assert response.json()["created_at"].endswith("Z")
    listed = client.get("/api/conversations").json()
    assert listed["items"][0]["created_at"].endswith("Z")


def test_symbol_topic_tokens_keep_word_boundaries():
    assert phrase_in_text("C++", "We use C++ for the service.")
    assert not phrase_in_text("C++", "We use C for the service.")
    assert phrase_in_text("launch", "The launch timeline is May.")
    assert not phrase_in_text("Tim", "The timeline is May.")
    assert phrase_in_text("Tim", "I asked Tim about the date.")


def test_colon_lines_continue_the_previous_message(client):
    transcript = "\n".join(
        [
            "Ava: See the notes.",
            "https://example.com/launch",
            "10:30 is too early.",
            "10:30am is too early.",
            "2026-03-02T10:30:00Z",
            "Bring the checklist.",
            "Bo: The launch timeline is May.",
            "2Pac: The encore starts now.",
        ]
    )
    response = client.post("/api/conversations/import", json={"title": "Notes", "transcript": transcript})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [item["speaker"] for item in messages] == ["Ava", "Bo", "2Pac"]
    assert "https://example.com/launch" in messages[0]["content"]
    assert "10:30 is too early." in messages[0]["content"]
    assert "10:30am is too early." in messages[0]["content"]
    assert "2026-03-02T10:30:00Z" in messages[0]["content"]
    assert "Bring the checklist." in messages[0]["content"]
    assert messages[1]["content"] == "The launch timeline is May."
    assert messages[2]["content"] == "The encore starts now."


def test_repeated_import_creates_a_new_conversation(client):
    payload = {"title": "Repeat", "transcript": "Ava: The launch timeline is May."}
    first = client.post("/api/conversations/import", json=payload).json()
    second = client.post("/api/conversations/import", json=payload).json()
    listing = client.get("/api/conversations").json()
    assert first["id"] != second["id"]
    assert listing["totals"]["conversations"] == 2
    assert {item["id"] for item in listing["items"]} == {first["id"], second["id"]}


def test_extract_uses_the_existing_conversation(client):
    payload = {"title": "Open", "transcript": "Ava: The launch timeline is May for the launch timeline review."}
    created = client.post("/api/conversations/import", json=payload).json()
    first = client.post(f"/api/conversations/{created['id']}/extract")
    second = client.post(f"/api/conversations/{created['id']}/extract")
    listing = client.get("/api/conversations").json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["conversation_id"] == created["id"]
    assert second.json()["conversation_id"] == created["id"]
    assert first.json()["extraction_run_id"] != second.json()["extraction_run_id"]
    assert listing["totals"]["conversations"] == 1


def _correction_payload() -> dict:
    return {
        "title": "Corrections",
        "messages": [
            {"speaker": "Ava", "content": "The launch timeline is May."},
            {"speaker": "Ben", "content": "Actually the launch timeline is April. This supersedes the May launch timeline."},
            {"speaker": "Cleo", "content": "The launch budget is fixed. Actually the launch date moved to June."},
        ],
    }


def _memory_id(graph: dict, text: str) -> str:
    matches = [node for node in graph["nodes"] if node["payload"].get("text") == text]
    assert len(matches) == 1
    return matches[0]["id"]


def _pairs(graph: dict, relation_type: str) -> list[dict[str, str]]:
    return [{"source": edge["source"], "target": edge["target"]} for edge in graph["edges"] if edge["type"] == relation_type]
