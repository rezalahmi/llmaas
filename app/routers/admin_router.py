#app\routers\admin_router.py
import secrets
import json
from fastapi import APIRouter, Depends
from app.redis_client import get_redis
from pydantic import BaseModel


class KeyCreate(BaseModel):
    user_id: int
    user: str
    quota: int

router = APIRouter(prefix="/admin")

@router.post("/keys")
async def create_key(data: KeyCreate, r=Depends(get_redis)):

    key = secrets.token_urlsafe(32)

    data = {
        "user_id": data.user_id,
        "user": data.user,
        "quota": data.quota
    }

    await r.set(f"api_key:{key}", json.dumps(data))

    return {
        "api_key": key,
        "data": data
    }


@router.get("/keys")
async def list_keys(r=Depends(get_redis)):

    keys = await r.keys("api_key:*")

    result = []

    for k in keys:
        if isinstance(k, bytes):
            k = k.decode()

        data = await r.get(k)

        if isinstance(data, bytes):
            data = data.decode()

        result.append({
            "key": k.replace("api_key:",""),
            "data": json.loads(data)
        })

    return result


@router.delete("/keys/{key}")
async def delete_key(key:str, r=Depends(get_redis)):

    await r.delete(f"api_key:{key}")

    return {"status":"deleted"}


@router.get("/usage/{user_id}")
async def get_usage(user_id:int, r=Depends(get_redis)):

    used = await r.get(f"usage:{user_id}")
    used = int(used or 0)

    return {
        "user_id": user_id,
        "tokens_used": used
    }
