# app\services\detach_file_service.py
import os
import chromadb
import time

chroma_client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./storage/chroma")
)


async def detach_file_from_vector_store(
    redis,
    vector_store_id: str,
    file_id: str,
    delete_file: bool = False
):

    vs_file_id = f"vsfile_{vector_store_id}_{file_id}"
    vs_key = f"vector_store_file:{vs_file_id}"

    # بررسی اتصال
    vs_meta = await redis.hgetall(vs_key)

    if not vs_meta:
        raise FileNotFoundError("File is not attached to this vector store")

    # --- 1. حذف chunk ها از Chroma ---
    collection = chroma_client.get_or_create_collection(
        name=vector_store_id,
        embedding_function=None
    )

    collection.delete(where={"file_id": file_id})

    # --- 2. حذف metadata اتصال ---
    await redis.delete(f"vector_store_file:{vs_file_id}")

    await redis.srem(
        f"vector_store_files:{vector_store_id}",
        vs_file_id
    )

    # --- 3. حذف فایل فیزیکی (اختیاری) ---
    if delete_file:

        file_meta = await redis.hgetall(f"file:{file_id}")

        if file_meta:

            file_path = file_meta.get("path")
            full_path = os.path.join(os.getcwd(), file_path)
            if file_path and os.path.exists(full_path):
                os.remove(full_path)

        await redis.delete(f"file:{file_id}")

    return {
        "id": vs_file_id,
        "vector_store_id": vector_store_id,
        "file_id": file_id,
        "status": "detached"
    }
