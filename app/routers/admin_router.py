# app/routers/admin_router.py

import secrets
from fastapi import APIRouter, Depends, HTTPException

from app.redis_client import get_redis
from app.postgres_client import get_pg
from app.schemas.admin import KeyCreate, KeyActiveUpdate
from app.dependencies import verify_admin
from app.security.api_keys import hash_api_key, api_key_prefix


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin)]
)


@router.post("/keys")
async def create_key(
    data: KeyCreate,
    pg=Depends(get_pg),
):
    raw_key = secrets.token_urlsafe(32)

    key_hash = hash_api_key(raw_key)
    key_prefix = api_key_prefix(raw_key)

    row = await pg.fetchrow(
        """
        insert into api_keys (
            external_user_id,
            user_name,
            key_prefix,
            key_hash,
            quota,
            is_active
        )
        values ($1, $2, $3, $4, $5, true)
        returning
            id,
            external_user_id,
            user_name,
            key_prefix,
            quota,
            is_active,
            created_at
        """,
        data.user_id,
        data.user,
        key_prefix,
        key_hash,
        data.quota,
    )

    return {
        "api_key": raw_key,
        "warning": "Store this API key now. It will not be shown again.",
        "data": dict(row),
    }


@router.get("/keys")
async def list_keys(
    pg=Depends(get_pg),
):
    rows = await pg.fetch(
        """
        select
            id,
            external_user_id,
            user_name,
            key_prefix,
            quota,
            is_active,
            created_at,
            last_used_at
        from api_keys
        order by created_at desc
        """
    )

    return [dict(row) for row in rows]


@router.delete("/keys/{key}")
async def delete_key(
    key: str,
    pg=Depends(get_pg),
):
    """
    این endpoint فعلاً با full raw key کار می‌کند.
    یعنی admin باید همان API key کامل را بدهد.
    ما hash می‌کنیم و رکورد را inactive می‌کنیم.
    """

    key_hash = hash_api_key(key)

    row = await pg.fetchrow(
        """
        update api_keys
        set is_active = false
        where key_hash = $1
        returning id, key_prefix, is_active
        """,
        key_hash,
    )

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "status": "deactivated",
        "key": dict(row),
    }


@router.get("/usage/{user_id}")
async def get_usage(
    user_id: int,
    r=Depends(get_redis),
):
    used = await r.get(f"usage:{user_id}")
    used = int(used or 0)

    return {
        "user_id": user_id,
        "tokens_used": used
    }


@router.delete("/keys/by-id/{key_id}")
async def delete_key_by_id(
    key_id: int,
    pg=Depends(get_pg),
):
    row = await pg.fetchrow(
        """
        update api_keys
        set is_active = false
        where id = $1
        returning id, key_prefix, is_active
        """,
        key_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "status": "deactivated",
        "key": dict(row),
    }



@router.post("/keys/by-id/{key_id}/activate")
async def activate_key_by_id(
    key_id: int,
    pg=Depends(get_pg),
):
    row = await pg.fetchrow(
        """
        update api_keys
        set is_active = true
        where id = $1
        returning id, key_prefix, is_active
        """,
        key_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "status": "activated",
        "key": dict(row),
    }



@router.patch("/keys/by-id/{key_id}")
async def set_key_active_by_id(
    key_id: int,
    data: KeyActiveUpdate,
    pg=Depends(get_pg),
):
    row = await pg.fetchrow(
        """
        update api_keys
        set is_active = $2
        where id = $1
        returning id, key_prefix, is_active
        """,
        key_id,
        data.is_active,
    )

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"status": "updated", "key": dict(row)}
