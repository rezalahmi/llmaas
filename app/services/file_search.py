# app\services\file_search.py
import os
import time
import chromadb
from typing import List, Dict, Any
from app.services.embedding_service import embed_text
from app.schemas.file_search import FileSearchQuery, FileSearchResultChunk, FileSearchResponse


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


# async def search_in_vector_store(query: FileSearchQuery) -> FileSearchResponse:
#     client = get_chroma_client()
#     all_raw_results: List[Dict[str, Any]] = []

#     query_embedding_vector = await embed_text(query.query)

#     search_k = max(query.max_results * 10, 50)

#     for vs_id in query.vector_store_ids:
#         try:
#             collection = client.get_collection(vs_id)
            
#             # جستجو با فیلتر
#             res = collection.query(
#                 query_embeddings=[query_embedding_vector],
#                 n_results=search_k,
#                 where=query.filters, # مطمئن شوید این قبل از رسیدن به اینجا به فرمت Chroma تبدیل شده است
#                 include=["documents", "metadatas", "distances"]
#             )

#             ids = res.get("ids", [[]])[0]
#             docs = res.get("documents", [[]])[0]
#             metas = res.get("metadatas", [[]])[0]
#             distances = res.get("distances", [[]])[0]

#             for doc_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
#                 all_raw_results.append({
#                     "file_id": meta.get("file_id", ""),
#                     "file_name": meta.get("file_name", ""),
#                     "vector_store_id": vs_id,
#                     "document_id": doc_id,
#                     "text": doc_text,
#                     "score": calculate_score_from_distance(dist),
#                     "metadata": meta or {},
#                     "distance": dist 
#                 })
#         except Exception as e:
#             print(f"Error querying collection {vs_id}: {e}")
#             continue

#     # منطق Deduplication اصلاح شده:
#     # همیشه بهترین چانک (کمترین distance) برای هر فایل را نگه می‌داریم
#     best_results_per_file = {}
#     for res in all_raw_results:
#         f_id = res["file_id"]
#         if f_id not in best_results_per_file or res["distance"] < best_results_per_file[f_id]["distance"]:
#             best_results_per_file[f_id] = res

#     # تبدیل به لیست و مرتب‌سازی بر اساس امتیاز نهایی
#     final_sorted_results = sorted(
#         best_results_per_file.values(), 
#         key=lambda x: x["score"], 
#         reverse=True
#     )[:query.max_results]

#     return FileSearchResponse(results=[
#         FileSearchResultChunk(
#             file_id=r["file_id"],
#             vector_store_id=r["vector_store_id"],
#             document_id=r["document_id"],
#             text=r["text"],
#             score=r["score"],
#             metadata=r["metadata"]
#         ) for r in final_sorted_results
#     ])

async def search_in_vector_store(query: FileSearchQuery) -> FileSearchResponse:
    client = get_chroma_client()
    all_raw_results: List[Dict[str, Any]] = []

    print(f"\n--- DEBUG START ---")
    print(f"Query Text: {query.query}")
    print(f"Original Filters: {query.filters}")
    print(f"Vector Store IDs: {query.vector_store_ids}")

    query_embedding_vector = await embed_text(query.query)
    search_k = max(query.max_results * 10, 50)

    for vs_id in query.vector_store_ids:
        try:
            collection = client.get_collection(vs_id)
            
            # --- بخش جدید دیباگ: دیدن دیتای واقعی داخل دیتابیس ---
            # بیا 2 تا آیتم اول دیتابیس رو بگیریم ببینیم متادیتای واقعی چیه
            sample = collection.get(limit=2, include=["metadatas"])
            print(f"Database Sample Metadata: {sample['metadatas']}")
            # --------------------------------------------------

            print(f"Executing Chroma Query with filter: {query.filters} (Type: {type(query.filters)})")
            
            res = collection.query(
                query_embeddings=[query_embedding_vector],
                n_results=search_k,
                where=query.filters,
                include=["documents", "metadatas", "distances"]
            )

            # لاگ نتیجه خام از کروما
            raw_ids = res.get("ids", [[]])[0]
            print(f"Chroma returned {len(raw_ids)} raw results for collection {vs_id}")

            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            for doc_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
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
            print(f"Error querying collection {vs_id}: {e}")
            import traceback
            traceback.print_exc() # چاپ جزئیات خطا
            continue

    print(f"Total results collected before deduplication: {len(all_raw_results)}")

    # منطق Deduplication
    best_results_per_file = {}
    for res in all_raw_results:
        f_id = res["file_id"]
        if f_id not in best_results_per_file or res["distance"] < best_results_per_file[f_id]["distance"]:
            best_results_per_file[f_id] = res

    final_sorted_results = sorted(
        best_results_per_file.values(), 
        key=lambda x: x["score"], 
        reverse=True
    )[:query.max_results]

    print(f"Final results count: {len(final_sorted_results)}")
    print(f"--- DEBUG END ---\n")

    return FileSearchResponse(results=[
        FileSearchResultChunk(
            file_id=r["file_id"],
            vector_store_id=r["vector_store_id"],
            document_id=r["document_id"],
            text=r["text"],
            score=r["score"],
            metadata=r["metadata"]
        ) for r in final_sorted_results
    ])
