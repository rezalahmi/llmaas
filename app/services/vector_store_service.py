# app\services\vector_store_service.py
import secrets
import time
import chromadb
import os
from fastapi import HTTPException

chroma_client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./storage/chroma")
)

def generate_vector_store_id():
    return f"vs_{secrets.token_urlsafe(16)}"


async def create_vector_store(redis, user_id: str, name: str | None):
    vector_store_id = generate_vector_store_id()

    data = {
        "id": vector_store_id,
        "user_id": user_id,
        "name": name,
        "created_at": int(time.time())
    }

    await redis.hset(
        f"vector_store:{vector_store_id}",
        mapping=data
    )

    await redis.sadd(
        f"user_vector_stores:{user_id}",
        vector_store_id
    )

    return data





async def delete_vector_store(redis, vector_store_id: str, delete_files: bool = False):

    vs_key = f"vector_store:{vector_store_id}"
    vs_meta = await redis.hgetall(vs_key)

    if not vs_meta:
        raise HTTPException(status_code=404, detail="Vector store not found")

    # حذف collection در Chroma
    try:
        chroma_client.delete_collection(name=vector_store_id)
    except Exception:
        pass

    # گرفتن فایل‌های attach شده
    vs_files_key = f"vector_store_files:{vector_store_id}"
    attached_files = await redis.smembers(vs_files_key)

    for vs_file_id in attached_files:

        await redis.delete(f"vector_store_file:{vs_file_id}")

        parts = vs_file_id.split("_")
        file_id = parts[-1]

        if delete_files:

            file_meta = await redis.hgetall(f"file:{file_id}")

            if file_meta:
                file_path = file_meta.get("path")

                if file_path:
                    full_path = os.path.join(os.getcwd(), file_path)

                    if os.path.exists(full_path):
                        os.remove(full_path)

            await redis.delete(f"file:{file_id}")

    await redis.delete(vs_files_key)

    await redis.delete(vs_key)

    await redis.srem("vector_stores", vector_store_id)

    return {
        "id": vector_store_id,
        "object": "vector_store.deleted",
        "deleted": True
    }




async def list_vector_store_files(redis, vector_store_id: str):

    vs_key = f"vector_store:{vector_store_id}"
    vs_meta = await redis.hgetall(vs_key)

    if not vs_meta:
        raise HTTPException(status_code=404, detail="Vector store not found")

    vs_files_key = f"vector_store_files:{vector_store_id}"
    vs_file_ids = await redis.smembers(vs_files_key)
    # --- DEBUG START ---
    print(f"DEBUG: Reading from key: {vs_files_key}")
    print(f"DEBUG: Found these IDs in Redis: {vs_file_ids}")
    # --- DEBUG END ---
    items = []

    for vs_file_id in vs_file_ids:
        prefix = f"vsfile_{vector_store_id}_"
        if not vs_file_id.startswith(prefix):
            continue

        file_id = vs_file_id[len(prefix):]
        print(f"DEBUG: Extracted file_id: {file_id}")

        # metadata فایل را بخوانیم
        file_meta = await redis.hgetall(f"file:{file_id}")

        if not file_meta:
            print(f"DEBUG: file_meta not found for {file_id}")
            continue

        created_at = int(file_meta.get("created_at", int(time.time())))

        items.append({
            "id": file_id,
            "object": "vector_store.file",
            "created_at": created_at,
            "vector_store_id": vector_store_id
        })

    items_sorted = sorted(items, key=lambda x: x["created_at"])

    return {
        "object": "list",
        "data": items_sorted,
        "first_id": items_sorted[0]["id"] if items_sorted else None,
        "last_id": items_sorted[-1]["id"] if items_sorted else None,
        "has_more": False
    }
