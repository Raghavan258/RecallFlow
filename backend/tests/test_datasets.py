"""Adapters keep benchmark answers out of the import payload."""

from app.datasets.adapters import adapt_locomo, adapt_longmemeval
from app.datasets.synthetic import load_synthetic


def test_synthetic_questions_are_not_in_the_import():
    conversation, questions = load_synthetic()
    blob = " ".join(item["content"] for item in conversation["messages"])
    assert "questions" not in conversation
    assert questions
    for question in questions:
        assert question["question"] not in blob
        assert "evidence_source_ids" not in conversation


def test_locomo_adapter_keeps_turns_and_separates_questions():
    sample = {
        "sample_id": "conv-1",
        "conversation": {
            "speaker_a": "Ada",
            "speaker_b": "Bo",
            "session_1_date_time": "2026-05-01T10:00:00Z",
            "session_1": [{"speaker": "Ada", "dia_id": "D1:1", "text": "The greenhouse is open."}],
            "observation": {"session_1_observation": "A generated observation that must not be imported."},
            "session_summary": {"session_1_summary": "A generated summary that must not be imported."},
        },
        "qa": [{"question": "Is the greenhouse open?", "answer": "yes", "category": 1, "evidence": ["D1:1"]}],
    }
    payload, questions = adapt_locomo(sample)
    assert payload["messages"][0]["source_id"] == "D1:1"
    assert payload["messages"][0]["timestamp"] == "2026-05-01T10:00:00Z"
    assert "generated observation" not in payload["messages"][0]["content"]
    assert questions[0]["evidence_source_ids"] == ["D1:1"]
    assert questions[0]["answer"] == "yes"
    assert "yes" not in payload["messages"][0]["content"]


def test_longmemeval_adapter_marks_answer_turns_only_in_the_eval_record():
    instance = {
        "question_id": "q1",
        "question_type": "knowledge-update",
        "question": "Where is the ticket?",
        "answer": "Kyoto",
        "haystack_session_ids": ["s1"],
        "haystack_dates": ["2026/05/20 14:30"],
        "haystack_sessions": [[{"role": "user", "content": "The ticket is for Kyoto.", "has_answer": True}]],
    }
    payload, questions = adapt_longmemeval(instance)
    assert payload["messages"][0]["source_id"] == "s1:0"
    assert payload["messages"][0]["timestamp"] == "2026-05-20T14:30:00Z"
    assert payload["messages"][0]["content"] == "The ticket is for Kyoto."
    assert questions[0]["answer"] == "Kyoto"
    assert questions[0]["evidence_source_ids"] == ["s1:0"]
    assert "Where is the ticket?" not in payload["messages"][0]["content"]
