import os
from typing import List
import chromadb
from app.services.embedding_service import embed_text
from app.schemas.file_search import FileSearchQuery, FileSearchResultChunk, FileSearchResponse

CHROMA_PATH = os.getenv("CHROMA_PATH", "./storage/chroma")




def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


async def search_in_vector_store(
    query: FileSearchQuery,
) -> FileSearchResponse:
    client = get_chroma_client()

    all_results: List[FileSearchResultChunk] = []
    
    query_embedding = await embed_text(query.query)
    # فعلاً ساده: روی همه vector_store_ids لوپ می‌زنیم و نتایج را merge می‌کنیم
    for vs_id in query.vector_store_ids:
        collection = client.get_collection(vs_id)

        res = collection.query(
            query_embeddings=[query_embedding],
            n_results=query.max_results,
            # بعداً: where / filters
        )

        # res ساختاری مثل:
        # {
        #   "ids": [[...]],
        #   "documents": [[...]],
        #   "metadatas": [[...]],
        #   "distances": [[...]],
        # }
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        for doc_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
            file_id = meta.get("file_id", "")
            score = float(dist)  # بسته به config، ممکن است similarity یا distance باشد

            chunk = FileSearchResultChunk(
                file_id=file_id,
                vector_store_id=vs_id,
                document_id=doc_id,
                text=doc_text,
                score=score,
                metadata=meta or {},
            )
            all_results.append(chunk)

    # TODO: اگر لازم است، sort بر اساس score، یا normalize
    all_results = sorted(all_results, key=lambda x: x.score)  # یا برعکس

    return FileSearchResponse(results=all_results[: query.max_results])
