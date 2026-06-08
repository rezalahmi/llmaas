# app\services\vector_store_service.py
import secrets
import time
import chromadb
import os
from fastapi import HTTPException

chroma_client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./storage/chroma")
)


def create_chroma_collection(collection_name: str):
    return chroma_client.get_or_create_collection(name=collection_name)


def delete_chroma_collection(collection_name: str):
    try:
        chroma_client.delete_collection(name=collection_name)
    except Exception:
        pass

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
        f"user_vs:{user_id}",
        vector_store_id
    )

    await redis.sadd(
        "vector_stores",
        vector_store_id
    )

    return data





async def delete_vector_store(redis, vector_store_id: str, user_id: str, delete_files: bool = False):

    vs_key = f"vector_store:{vector_store_id}"
    vs_meta = await redis.hgetall(vs_key)



    if not vs_meta:
        raise HTTPException(status_code=404, detail="Vector store not found")

    owner_id = vs_meta.get("user_id") or vs_meta.get(b"user_id")
    if isinstance(owner_id, bytes):
        owner_id = owner_id.decode("utf-8")

    if str(owner_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")    
    

    # حذف collection در Chroma
    try:
        chroma_client.delete_collection(name=vector_store_id)
    except Exception:
        pass

    # گرفتن فایل‌های attach شده
    vs_files_key = f"vector_store_files:{vector_store_id}"
    attached_files = await redis.smembers(vs_files_key)

    for vs_file_id in attached_files:
        if isinstance(vs_file_id, bytes):
            vs_file_id = vs_file_id.decode("utf-8")

        await redis.delete(f"vector_store_file:{vs_file_id}")

        parts = vs_file_id.split("_")
        file_id = parts[-1]

        if delete_files:

            file_meta = await redis.hgetall(f"file:{file_id}")

            if file_meta:
                file_path = file_meta.get("path") or file_meta.get(b"path")
                if isinstance(file_path, bytes):
                    file_path = file_path.decode("utf-8")

                if file_path:
                    full_path = os.path.join(os.getcwd(), file_path)

                    if os.path.exists(full_path):
                        os.remove(full_path)

            await redis.delete(f"file:{file_id}")

    await redis.delete(vs_files_key)
    await redis.delete(vs_key)

    await redis.srem(f"user_vs:{user_id}", vector_store_id)
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



async def get_vector_stores_for_owner(pg, api_key_id: str, vector_store_ids: list[str]):
    if not vector_store_ids:
        return []

    query = """
        SELECT id
        FROM vector_stores
        WHERE api_key_id = $1
          AND id = ANY($2::text[])
          AND deleted_at IS NULL
    """
    return await pg.fetch(query, api_key_id, vector_store_ids)