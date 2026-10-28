"""API coverage for import, extraction, graph reads, and failures."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.extraction.baseline import BaselineExtractor
from app.extraction.types import ExtractionResult
from app.models import Memory


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_import_preserves_order_sources_and_missing_timestamp(client, sample_payload):
    created = client.post("/api/conversations/import", json=sample_payload)
    assert created.status_code == 200
    body = created.json()
    assert body["title"] == "Nimbus launch planning"
    assert body["source_format"] == "json"
    assert [item["source_id"] for item in body["messages"]] == [f"m{index}" for index in range(1, 12)]
    assert [item["position"] for item in body["messages"]] == list(range(11))
    assert body["messages"][0]["timestamp"] is not None
    assert body["messages"][7]["timestamp"] is None
    assert body["messages"][7]["speaker"] == "Ben"


def test_paste_import_and_continuation(client):
    transcript = "Ada [2026-04-01T10:00:00Z]: Started the migration.\nThe second line stays with Ada.\n\nBo: No timestamp here."
    response = client.post("/api/conversations/import", json={"title": "Notes", "transcript": transcript})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert messages[0]["speaker"] == "Ada"
    assert "second line" in messages[0]["content"]
    assert messages[0]["timestamp"] is not None
    assert messages[1]["speaker"] == "Bo"
    assert messages[1]["timestamp"] is None
    assert messages[1]["source_id"] is None


def test_invalid_import_and_unknown_records(client):
    empty = client.post("/api/conversations/import", json={})
    assert empty.status_code == 422
    assert "transcript" in empty.json()["detail"].lower() or "messages" in empty.json()["detail"].lower()
    broken = client.post("/api/conversations/import", json={"transcript": "this line has no speaker"})
    assert broken.status_code == 422
    missing = client.post("/api/conversations/missing/extract")
    assert missing.status_code == 404
    assert client.get("/api/memories/missing").status_code == 404
    assert client.get("/api/conversations/missing/graph").status_code == 404


def test_sample_extraction_graph_and_traceability(client, sample_payload):
    created = client.post("/api/conversations/import", json=sample_payload).json()
    extracted = client.post(f"/api/conversations/{created['id']}/extract")
    assert extracted.status_code == 200
    graph = extracted.json()
    labels = {node["label"] for node in graph["nodes"] if node["type"] == "topic"}
    assert len(labels & {"Onboarding", "Privacy", "Pricing", "Launch"}) >= 3
    _assert_multi_topic_memory(client, graph)
    _assert_traceability(created["messages"], graph)
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert edge_types >= {
        "CONTAINS",
        "DERIVED_FROM",
        "RELATED_TO",
        "MENTIONS",
        "SUPPORTS",
        "DEPENDS_ON",
        "SUPERSEDES",
        "CONTRADICTS",
    }
    topics = client.get("/api/topics", params={"conversation_id": created["id"]})
    assert topics.status_code == 200
    assert len(topics.json()) >= 3


def test_history_is_kept_when_extraction_runs_again(client, sample_payload):
    created = client.post("/api/conversations/import", json=sample_payload).json()
    first = client.post(f"/api/conversations/{created['id']}/extract").json()
    client.post(f"/api/conversations/{created['id']}/extract")
    latest = client.get(f"/api/conversations/{created['id']}/graph").json()
    assert len(_memories(latest)) == len(_memories(first))
    with Session(client.app.state.engine) as session:
        stored = session.scalar(select(func.count()).select_from(Memory))
    assert stored == len(_memories(first)) * 2


def test_database_persists_across_app_instances(tmp_path, sample_payload):
    database = tmp_path / "shared.db"
    settings = _settings(database.as_posix())
    with TestClient(_app(settings)) as first:
        created = first.post("/api/conversations/import", json=sample_payload)
        conversation_id = created.json()["id"]
    first.app.state.engine.dispose()
    with TestClient(_app(settings)) as second:
        loaded = second.get(f"/api/conversations/{conversation_id}")
        assert loaded.status_code == 200
        assert len(loaded.json()["messages"]) == 11
    second.app.state.engine.dispose()


def test_invalid_extractor_output_is_rejected(client, sample_payload, monkeypatch):
    created = client.post("/api/conversations/import", json=sample_payload).json()

    def _bad(self, messages):
        return ExtractionResult(provider="baseline", limitations=[], topics=[], memories=[], entities=[], relationships=[])

    monkeypatch.setattr(BaselineExtractor, "extract", _bad)
    # An empty extraction is valid. Force a dangling relationship through validate by patching it.
    from app.services import extraction_service

    def _invalid(result, message_ids):
        from app.errors import ExtractionError

        raise ExtractionError("A relationship source does not exist in the extraction.")

    monkeypatch.setattr(extraction_service, "validate_extraction", _invalid)
    response = client.post(f"/api/conversations/{created['id']}/extract")
    assert response.status_code == 422
    assert "relationship" in response.json()["detail"].lower()
    follow = client.get(f"/api/conversations/{created['id']}/graph")
    assert follow.json()["nodes"] == []


def _assert_multi_topic_memory(client, graph: dict) -> None:
    memories = [node for node in graph["nodes"] if node["type"] in {"memory", "decision"}]
    multi = [node for node in memories if len(node["topic_ids"]) >= 2]
    assert multi
    detail = client.get(f"/api/memories/{multi[0]['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["topics"]) >= 2
    assert detail.json()["source_messages"]


def _assert_traceability(messages: list[dict], graph: dict) -> None:
    by_id = {item["id"]: item["content"] for item in messages}
    derived = [edge for edge in graph["edges"] if edge["type"] == "DERIVED_FROM"]
    assert derived
    for edge in derived:
        content = by_id[edge["target"]]
        memory = next(node for node in graph["nodes"] if node["id"] == edge["source"])
        assert memory["payload"]["text"].rstrip(".?") in content


def _memories(graph: dict) -> list[dict]:
    return [node for node in graph["nodes"] if node["type"] in {"memory", "decision"}]


def _settings(path: str):
    from app.config import settings_for_tests

    return settings_for_tests(f"sqlite:///{path}")


def _app(settings):
    from app.main import create_app

    return create_app(settings)
