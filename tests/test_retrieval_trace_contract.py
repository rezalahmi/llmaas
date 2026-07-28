import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.retrieval_trace import (
    RetrievalFailure,
    RetrievalStageName,
    RetrievalTraceEvent,
)


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


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_contract_fixtures_validate(fixture_path: Path):
    event = RetrievalTraceEvent.model_validate(load_fixture(fixture_path))
    assert event.schema_version == "1.0"
    assert event.metrics.attempt_count >= 1
    assert event.metrics.query_rewrite_count >= 0
    assert event.versions.index_version or event.versions.corpus_revision
    assert event.confidence.answer_confidence is None
    assert event.confidence.confidence_status == "not_supported"
    assert not (set(all_keys(event.model_dump())) & PROHIBITED_FIELDS)


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


def test_stage_taxonomy_and_stage_failures_are_locked():
    assert {item.value for item in RetrievalStageName} == {
        "query_rewrite",
        "dense_retrieval",
        "filtering",
        "reranking",
        "context_selection",
    }
    payload = load_fixture(FIXTURE_DIR / "failed-fa.json")
    payload["stages"][1]["failure"] = None
    with pytest.raises(ValidationError, match="failed stage"):
        RetrievalTraceEvent.model_validate(payload)


def test_schema_rejects_unknown_or_sensitive_fields():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    for field in PROHIBITED_FIELDS:
        invalid = {**payload, field: "must-not-leak"}
        with pytest.raises(ValidationError):
            RetrievalTraceEvent.model_validate(invalid)


def test_attempts_and_rewrites_share_one_session_trace_id():
    payload = load_fixture(FIXTURE_DIR / "empty-fa.json")
    event = RetrievalTraceEvent.model_validate(payload)
    assert event.metrics.attempt_count == 2
    assert event.metrics.query_rewrite_count == 1
    assert event.trace_id == payload["trace_id"]
    assert "attempt_id" not in set(all_keys(event.model_dump()))
    assert "rewritten_query" not in set(all_keys(event.model_dump()))


def test_index_or_corpus_revision_is_required():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    payload["versions"]["index_version"] = None
    payload["versions"]["corpus_revision"] = None
    with pytest.raises(ValidationError, match="index_version or corpus_revision"):
        RetrievalTraceEvent.model_validate(payload)


def test_retrieval_dependency_versions_are_required_and_atomic():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    del payload["versions"]["retrieval_pipeline_version"]
    with pytest.raises(ValidationError):
        RetrievalTraceEvent.model_validate(payload)

    payload = load_fixture(FIXTURE_DIR / "empty-fa.json")
    payload["versions"]["query_rewriter_version"] = None
    with pytest.raises(ValidationError, match="query_rewriter"):
        RetrievalTraceEvent.model_validate(payload)


def test_selected_sources_have_unique_source_chunk_attribution():
    payload = load_fixture(FIXTURE_DIR / "success-en.json")
    payload["retrieved_sources"].append(dict(payload["retrieved_sources"][0]))
    payload["metrics"]["candidate_count"] = 2
    payload["metrics"]["selected_count"] = 2
    with pytest.raises(ValidationError, match="attribution"):
        RetrievalTraceEvent.model_validate(payload)


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
