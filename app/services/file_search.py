# app\services\file_search.py
import os
import logging
import chromadb
from collections import defaultdict
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.services.embedding_service import embed_text
from app.schemas.file_search import FileSearchQuery, FileSearchResultChunk, FileSearchResponse


logger = logging.getLogger(__name__)

CHROMA_PATH = os.getenv("CHROMA_PATH", "./storage/chroma")

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

# --- تابع کمکی برای محاسبه score از distance ---
def calculate_score_from_distance(distance: float) -> float:
    """
    Converts distance (e.g., from cosine similarity) to a score where higher is better.
    Assumes distance is between 0 and 2 for cosine similarity. Adjust if using other metrics.
    """
    # این فرمول برای cosine distance مناسب است. اگر از L2 یا IP استفاده میکنی، باید تغییر کند.
    # اگر distance بین 0 و 1 است (مثلا در some metrics)، این فرمول باید 1 - distance باشد.
    # برای اطمینان، مقدار را بین 0 و 1 نگه می‌داریم.
    score = 1.0 - distance
    return max(0.0, min(1.0, score)) # اطمینان از اینکه score بین 0 و 1 است



async def search_in_vector_store(query: FileSearchQuery) -> FileSearchResponse:
    
    try:
        client = get_chroma_client()
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        raise HTTPException(status_code=503, detail="Vector database service is unavailable")
                            
    all_raw_results: List[Dict[str, Any]] = []


    # 1. مرحله Embedding
    try:
        query_embedding_vector = await embed_text(query.query)
    except Exception as e:
        logger.error(f"Embedding failed for query '{query.query}': {e}")
        raise HTTPException(status_code=502, detail="Failed to generate embeddings for the search query")
    

    search_k = max(query.max_results * 10, 50)

    # 2. جستجو در تک تک کالکشن‌ها
    for vs_id in query.vector_store_ids:
        try:
            try:
                collection = client.get_collection(vs_id)
            except Exception as e:
                    # اگر کالکشن پیدا نشد (معمولاً ValueError یا KeyError بسته به نسخه Chroma)
                    logger.warning(f"Collection {vs_id} not found. Skipping. Error: {e}")
                    continue 
            # اجرای کوئری            
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
                # اطمینان از وجود متادیتاهای حیاتی
                file_id = meta.get("file_id") if meta else None
                if not file_id:
                    logger.debug(f"Chunk {doc_id} in {vs_id} missing file_id metadata. Skipping.")
                    continue

                all_raw_results.append({
                    "file_id": meta.get("file_id", ""),
                    "file_name": meta.get("file_name", ""),
                    "vector_store_id": vs_id,
                    "document_id": doc_id,
                    "text": doc_text,
                    "score": calculate_score_from_distance(dist),
                    "metadata": meta or {},
                    "distance": dist 
                })
        except Exception as e:
            logger.error(f"Error querying collection {vs_id}: {str(e)}", exc_info=True)
            continue
    
    if not all_raw_results:
        return FileSearchResponse(results=[])
    

    # منطق Deduplication
    sorted_results = sorted(
        all_raw_results,
        key=lambda x: x["score"],
        reverse=True
    )

    per_file = defaultdict(list)

    for r in sorted_results:
        per_file[r["file_id"]].append(r)

    final_results = []

    # مرحله 1: بهترین نتیجه از هر فایل
    for file_id, chunks in per_file.items():
        final_results.append(chunks[0])

    # مرحله 2: اگر هنوز جا بود، بقیه چانک‌ها
    if len(final_results) < query.max_results:
        for file_id, chunks in per_file.items():
            for c in chunks[1:]:
                final_results.append(c)
                if len(final_results) >= query.max_results:
                    break
            if len(final_results) >= query.max_results:
                break

    final_results = sorted(
        final_results,
        key=lambda x: x["score"],
        reverse=True
    )[:query.max_results]


    return FileSearchResponse(results=[
        FileSearchResultChunk(
            file_id=r["file_id"],
            vector_store_id=r["vector_store_id"],
            document_id=r["document_id"],
            text=r["text"],
            score=r["score"],
            metadata=r["metadata"]
        ) for r in final_results
    ])
