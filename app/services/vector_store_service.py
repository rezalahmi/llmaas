import secrets
import time


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
