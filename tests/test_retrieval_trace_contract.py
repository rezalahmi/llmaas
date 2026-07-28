import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.retrieval_trace import RetrievalFailure, RetrievalTraceEvent


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "retrieval_trace" / "v1"
FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))
PROHIBITED_FIELDS = {
    "api_key",
    "chunk_content",
    "content",
    "exception",
    "model_answer",
    "prompt",
    "provider_response",
    "query",
    "raw_query",
    "selected_context",
}


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_contract_fixtures_validate(fixture_path: Path):
    event = RetrievalTraceEvent.model_validate(load_fixture(fixture_path))
    assert event.schema_version == "1.0"
    assert event.confidence.answer_confidence is None
    assert event.confidence.confidence_status == "not_supported"


def test_fixtures_cover_required_scenarios_and_languages():
    fixture_names = {path.stem for path in FIXTURES}
    assert {name.split("-")[0] for name in fixture_names} == {
        "success",
        "empty",
        "degraded",
        "failed",
    }
    assert {name.split("-")[1] for name in fixture_names} == {"en", "fa"}


def test_failure_taxonomy_is_locked():
    assert {item.value for item in RetrievalFailure} == {
        "no_candidates",
        "below_relevance_threshold",
        "filter_eliminated_all",
        "reranker_eliminated_all",
        "source_unavailable",
        "index_unavailable",
        "timeout",
        "provider_error",
        "unknown",
    }


def test_schema_rejects_unknown_or_sensitive_fields():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    for field in PROHIBITED_FIELDS:
        invalid = {**payload, field: "must-not-leak"}
        with pytest.raises(ValidationError):
            RetrievalTraceEvent.model_validate(invalid)


def test_schema_rejects_count_or_selection_drift():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    payload["metrics"]["selected_count"] = 0
    with pytest.raises(ValidationError, match="selected_count"):
        RetrievalTraceEvent.model_validate(payload)


def test_schema_rejects_false_confidence():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    payload["confidence"]["answer_confidence"] = 0.86
    payload["confidence"]["confidence_status"] = "available"
    with pytest.raises(ValidationError):
        RetrievalTraceEvent.model_validate(payload)


def test_json_schema_snapshot_is_current():
    schema_path = (
        Path(__file__).parents[1]
        / "docs"
        / "contracts"
        / "retrieval-trace-event-v1.schema.json"
    )
    checked_in_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert checked_in_schema == RetrievalTraceEvent.model_json_schema()
