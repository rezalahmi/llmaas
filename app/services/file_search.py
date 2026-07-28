import os
import logging
import chromadb
from collections import defaultdict
from typing import List, Dict, Any
from fastapi import HTTPException
from app.services.embedding_service import embed_text
from app.schemas.file_search import (
    FileSearchQuery,
    FileSearchResultChunk,
    FileSearchResponse,
)
from app.services.reranker_service import rerank_results
from app.services.retrieval_facts import build_retrieval_candidate_facts

logger = logging.getLogger(__name__)

CHROMA_PATH = os.getenv("CHROMA_PATH", "/data/chroma")


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


def calculate_score_from_distance(distance: float) -> float:
    score = 1.0 - distance
    return max(0.0, min(1.0, score))


async def search_in_vector_store(query: FileSearchQuery) -> FileSearchResponse:
    try:
        client = get_chroma_client()
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Vector database service is unavailable")

    all_raw_results: List[Dict[str, Any]] = []

    try:
        query_embedding_vector = await embed_text(query.query)
    except Exception as e:
        logger.error("Embedding failed for a search query", exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to generate embeddings for the search query")

    max_results = query.max_results or 10
    search_k = max(max_results * 10, 50)

    for vs_id in query.vector_store_ids:
        try:
            try:
                collection = client.get_collection(vs_id)
            except Exception as e:
                logger.warning(f"Collection {vs_id} not found. Skipping. Error: {e}")
                continue

            res = collection.query(
                query_embeddings=[query_embedding_vector],
                n_results=search_k,
                where=query.filters,
                include=["documents", "metadatas", "distances"]
            )

            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            for doc_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
                file_id = meta.get("file_id") if meta else None
                if not file_id:
                    logger.debug(f"Chunk {doc_id} in {vs_id} missing file_id metadata. Skipping.")
                    continue

                all_raw_results.append({
                    "file_id": meta.get("file_id", ""),
                    "file_name": meta.get("file_name", ""),
                    "vector_store_id": vs_id,
                    "document_id": doc_id,
                    "chunk_ref": meta.get("chunk_ref", doc_id),
                    "text": doc_text,
                    "score": calculate_score_from_distance(dist),
                    "dense_score": None,
                    "rerank_score": None,
                    "dense_rank": None,
                    "rerank_rank": None,
                    "dense_distance": dist,
                    "metadata": meta or {},
                    "distance": dist,
                })

        except Exception as e:
            logger.error(f"Error querying collection {vs_id}: {str(e)}", exc_info=True)
            continue

    if not all_raw_results:
        logger.info("[search] No results found")
        return FileSearchResponse(results=[])

    all_raw_results.sort(key=lambda item: item["dense_distance"])
    for dense_rank, item in enumerate(all_raw_results, start=1):
        item["dense_rank"] = dense_rank

    reranked_results = await rerank_results(query.query, all_raw_results)
    sorted_results = reranked_results if reranked_results else all_raw_results

    per_file = defaultdict(list)
    for r in sorted_results:
        per_file[r["file_id"]].append(r)

    final_results = []

    for file_id, chunks in per_file.items():
        if chunks:
            final_results.append(chunks[0])

    if len(final_results) < max_results:
        for file_id, chunks in per_file.items():
            for c in chunks[1:]:
                final_results.append(c)
                if len(final_results) >= max_results:
                    break
            if len(final_results) >= max_results:
                break

    final_results = sorted(
        final_results,
        key=lambda x: x["score"],
        reverse=True
    )[:max_results]

    retrieval_facts = build_retrieval_candidate_facts(
        all_raw_results,
        final_results,
    )

    return FileSearchResponse(results=[
        FileSearchResultChunk(
            file_id=r["file_id"],
            vector_store_id=r["vector_store_id"],
            document_id=r["document_id"],
            chunk_ref=r["chunk_ref"],
            text=r["text"],
            score=r["score"],
            dense_score=r.get("dense_score"),
            rerank_score=r.get("rerank_score"),
            dense_rank=r.get("dense_rank"),
            rerank_rank=r.get("rerank_rank"),
            dense_distance=r.get("dense_distance"),
            metadata=r["metadata"]
        )
        for r in final_results
    ], retrieval_facts=retrieval_facts)
