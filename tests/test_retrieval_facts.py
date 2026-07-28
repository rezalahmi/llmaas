from app.services.retrieval_facts import build_retrieval_candidate_facts


def test_candidate_and_selected_context_facts_are_distinct_and_content_free():
    candidates = [
        {
            "file_id": "file_1",
            "chunk_ref": "chk_1",
            "vector_store_id": "vs_1",
            "dense_distance": 0.2,
            "dense_rank": 1,
            "rerank_score": 0.8,
            "rerank_rank": 1,
            "text": "must not enter facts",
        },
        {
            "file_id": "file_2",
            "chunk_ref": "chk_2",
            "vector_store_id": "vs_1",
            "dense_distance": 0.3,
            "dense_rank": 2,
            "rerank_score": 0.7,
            "rerank_rank": 2,
            "text": "must not enter facts",
        },
    ]

    facts = build_retrieval_candidate_facts(candidates, [candidates[0]])
    payloads = [fact.model_dump() for fact in facts]

    assert [fact.candidate for fact in facts] == [True, True]
    assert [fact.selected for fact in facts] == [True, False]
    assert all(fact.dense_relevance_score is None for fact in facts)
    assert all("text" not in payload for payload in payloads)
    assert payloads[0]["source_id"] == "file_1"
    assert payloads[0]["chunk_ref"] == "chk_1"
