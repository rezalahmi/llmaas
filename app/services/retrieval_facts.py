"""Build content-free candidate and selection facts from retrieval results."""

from typing import Any

from app.schemas.file_search import RetrievalCandidateFact


def build_retrieval_candidate_facts(
    candidates: list[dict[str, Any]],
    selected_results: list[dict[str, Any]],
) -> list[RetrievalCandidateFact]:
    selected_refs = {
        (item["vector_store_id"], item["chunk_ref"]) for item in selected_results
    }
    return [
        RetrievalCandidateFact(
            source_id=item["file_id"],
            chunk_ref=item["chunk_ref"],
            vector_store_id=item["vector_store_id"],
            dense_distance=item["dense_distance"],
            dense_rank=item["dense_rank"],
            dense_relevance_score=None,
            rerank_score=item.get("rerank_score"),
            rerank_rank=item.get("rerank_rank"),
            selected=(item["vector_store_id"], item["chunk_ref"]) in selected_refs,
        )
        for item in candidates
    ]
