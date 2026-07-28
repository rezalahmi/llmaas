import os
from typing import Optional
import chromadb
from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.embedding_service import embed_texts
from app.services.Extractors.master_extractor import EXTRACTORS
from app.services.vector_store_metadata_service import upsert_vector_store_file
from app.repositories.chunk_repository import (
    delete_chunk_inventory,
    replace_chunk_inventory,
)
from app.services.chunk_identity import assign_chunk_refs
from app.services.retrieval_version_service import (
    get_retrieval_dependency_versions,
)
from app.token_counter import count_tokens

chroma_client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./storage/chroma")
)

async def attach_file_to_vector_store(
    pg,
    vector_store_id: str,
    file_id: str,
    file_record: dict,
    chunk_size: int,
    chunk_overlap: int,
    batch_id: Optional[str] = None,
):
    dependency_versions = get_retrieval_dependency_versions()
    # مسیر فایل از رکورد Postgres خوانده می‌شود
    # فرض می‌کنیم در Postgres ستون storage_path داریم: storage/files/file_id.pdf
    file_path = file_record["storage_path"]
    file_name = file_record["filename"]
    ext = file_record["ext"] # مثلاً .pdf
    
    full_path = os.path.join(os.getcwd(), file_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found at: {full_path}")
    
    # ۱. استخراج متن
    extractor = EXTRACTORS.get(ext if ext.startswith('.') else f".{ext}")
    if not extractor:
        raise ValueError(f"Extension {ext} is not supported.")
    
    raw_documents = extractor(full_path)

    # ۲. Chunking
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    final_chunks = []
    final_metadatas = []
    global_chunk_index = 0
    
    for doc in raw_documents:
        if ext in [".xlsx", ".xls", ".pptx"]:
            chunks = [doc["text"]]
        else:
            chunks = splitter.split_text(doc["text"])

        for chunk_text in chunks:
            if not chunk_text.strip(): continue
            final_chunks.append(chunk_text)
            
            meta = {
                "file_id": file_id,
                "file_name": file_name,
                "chunk_index": global_chunk_index
            }
            if "metadata" in doc:
                meta.update(doc["metadata"])
            
            final_metadatas.append(meta)
            global_chunk_index += 1
    
    if not final_chunks:
        raise HTTPException(status_code=400, detail="No extractable text found.")

    # ۳. تولید Embedding
    embeddings = await embed_texts(final_chunks)

    # ۴. ذخیره در Chroma
    collection = chroma_client.get_or_create_collection(
        name=vector_store_id,
        embedding_function=None
    )

    # Keep previous IDs until the replacement has been written successfully.
    # This prevents a failed upsert from making an existing attachment empty.
    existing = collection.get(
        where={"file_id": file_id},
        include=["metadatas"],
    )
    existing_ids = set(existing.get("ids") or [])

    chunking_parameters = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    chunk_identities = assign_chunk_refs(
        final_chunks,
        api_key_id=file_record["api_key_id"],
        file_id=file_id,
        chunking_strategy=dependency_versions.chunking_strategy,
        chunking_version=dependency_versions.chunking_version,
        chunking_parameters=chunking_parameters,
    )
    ids = [chunk_ref for chunk_ref, _ in chunk_identities]
    for metadata, chunk_ref in zip(final_metadatas, ids):
        metadata.update(
            {
                "chunk_ref": chunk_ref,
                "chunking_strategy": dependency_versions.chunking_strategy,
                "chunking_version": dependency_versions.chunking_version,
                "embedding_model": dependency_versions.embedding_model,
                "embedding_version": dependency_versions.embedding_version,
                "vector_index_provider": dependency_versions.vector_index_provider,
                "vector_index_version": dependency_versions.vector_index_version,
            }
        )
    
    collection.upsert(
        ids=ids,
        documents=final_chunks,
        embeddings=embeddings,
        metadatas=final_metadatas
    )
    stale_ids = sorted(existing_ids - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)

    await replace_chunk_inventory(
        pg,
        api_key_id=file_record["api_key_id"],
        vector_store_id=vector_store_id,
        file_id=file_id,
        chunks=[
            {
                "id": chunk_id,
                "chunk_ref": chunk_id,
                "chunk_index": metadata["chunk_index"],
                "chunking_strategy": dependency_versions.chunking_strategy,
                "chunking_version": dependency_versions.chunking_version,
                "embedding_model": dependency_versions.embedding_model,
                "embedding_version": dependency_versions.embedding_version,
                "reranker_model": dependency_versions.reranker_model,
                "reranker_version": dependency_versions.reranker_version,
                "generation_model": dependency_versions.generation_model,
                "generation_version": dependency_versions.generation_version,
                "vector_index_provider": (
                    dependency_versions.vector_index_provider
                ),
                "vector_index_version": (
                    dependency_versions.vector_index_version
                ),
                "character_count": len(chunk_text),
                "token_count": count_tokens(chunk_text),
                "exact_hash": exact_hash,
                "metadata": metadata,
            }
            for chunk_id, exact_hash, chunk_text, metadata in zip(
                ids,
                (exact_hash for _, exact_hash in chunk_identities),
                final_chunks,
                final_metadatas,
            )
        ],
    )

    # ۵. آپدیت وضعیت در Postgres به ready
    # از همان تابعی که در فایل قبلی نوشتیم با وضعیت 'ready' استفاده می‌کنیم
    db_row = await upsert_vector_store_file(
        pg,
        vector_store_id=vector_store_id,
        file_id=file_id,
        external_user_id=file_record["external_user_id"],
        api_key_id=file_record["api_key_id"],
        status="ready",
        batch_id=batch_id,
        error=None,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return {
        "id": db_row["id"],
        "object": "vector_store.file",
        "vector_store_id": vector_store_id,
        "file_id": file_id,
        "created_at": int(db_row["created_at"].timestamp()),
        "status": "ready"
    }

async def detach_file_from_vector_store_pg(
    pg,
    vector_store_id: str,
    file_id: str,
    api_key_id: str,
    delete_file: bool = False
):
    """
    - بررسی مالکیت vector store
    - بررسی وجود attachment
    - حذف از Chroma (docs where file_id)
    - حذف attachment از DB
    - (اختیاری) حذف خود فایل از DB/Storage
    """

    # ۱) بررسی مالکیت vector store
    vs = await pg.fetchrow(
        "SELECT id FROM vector_stores WHERE id=$1 AND api_key_id=$2",
        vector_store_id, api_key_id
    )
    if not vs:
        # اگر می‌خواهید فرق 404/403 بدهید، می‌توانید جدا کنید
        raise FileNotFoundError()

    # ۲) بررسی اینکه فایل attach شده
    attached = await pg.fetchrow(
        """
        SELECT id FROM vector_store_files
        WHERE vector_store_id=$1 AND file_id=$2
        """,
        vector_store_id, file_id
    )
    if not attached:
        raise FileNotFoundError()

    # ۳) حذف از Chroma
    collection = chroma_client.get_or_create_collection(name=vector_store_id)
    collection.delete(where={"file_id": file_id})
    await delete_chunk_inventory(
        pg,
        api_key_id=api_key_id,
        vector_store_id=vector_store_id,
        file_id=file_id,
    )

    # ۴) حذف attachment از DB
    await pg.execute(
        """
        DELETE FROM vector_store_files
        WHERE vector_store_id=$1 AND file_id=$2
        """,
        vector_store_id, file_id
    )

    # ۵) اگر delete_file=True بود: حذف خود فایل (اختیاری و بسته به منطق شما)
    if delete_file:
        # توصیه: فقط اگر فایل به هیچ vector store دیگری attach نیست حذف شود
        still_used = await pg.fetchrow(
            "SELECT 1 FROM vector_store_files WHERE file_id=$1 LIMIT 1",
            file_id
        )
        if not still_used:
            # اینجا بسته به معماری شما:
            # - حذف از جدول files
            # - حذف از disk/S3
            await pg.execute(
                "DELETE FROM files WHERE id=$1 AND api_key_id=$2",
                file_id, api_key_id
            )
            # حذف فیزیکی از storage را اگر دارید، اینجا اضافه کنید

    return {
        "object": "vector_store.file.deleted",
        "vector_store_id": vector_store_id,
        "file_id": file_id,
        "deleted": True
    }
