# app/routers/admin_router.py

import secrets
from fastapi import APIRouter, Depends, HTTPException, Query

from app.redis_client import get_redis
from app.postgres_client import get_pg
from app.schemas.admin import KeyCreate, KeyActiveUpdate
from app.dependencies import verify_admin
from app.security.api_keys import hash_api_key, api_key_prefix
from app.services.usage_service import get_user_usage_service, get_admin_user_usage_service
from app.schemas.quota import CreditQuotaRequest, DebitQuotaRequest
from app.services.quota_service import (
    credit_api_key_service,
    consume_api_key_quota_service,
    get_key_quota_service,
    get_user_quota_summary_service,
    list_key_quota_ledger_service,
)


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
async def get_usage_endpoint(
    user_id: int,
    pg=Depends(get_pg),
    redis=Depends(get_redis)
):
     return await get_admin_user_usage_service(pg, redis, user_id=user_id)
    


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


@router.post("/keys/by-id/{key_id}/credit")
async def credit_key_by_id(
    key_id: int,
    body: CreditQuotaRequest,
    pg_pool=Depends(get_pg),
):
    return await credit_api_key_service(
        pg_pool,
        key_id=key_id,
        amount=body.amount,
        reason=body.reason,
        reference_id=body.reference_id,
    )


@router.post("/keys/by-id/{key_id}/debit")
async def debit_key_by_id(
    key_id: int,
    body: DebitQuotaRequest,
    pg_pool=Depends(get_pg),
):
    return await consume_api_key_quota_service(
        pg_pool,
        key_id=key_id,
        amount=body.amount,
        reason=body.reason,
        reference_id=body.reference_id,
    )


@router.get("/keys/by-id/{key_id}/quota")
async def get_key_quota_endpoint(
    key_id: int,
    pg_pool=Depends(get_pg),
):
    return await get_key_quota_service(pg_pool, key_id=key_id)


@router.get("/users/{user_id}/quota")
async def get_user_quota_endpoint(
    user_id: int,
    pg_pool=Depends(get_pg),
):
    return await get_user_quota_summary_service(
        pg_pool,
        external_user_id=user_id,
    )


@router.get("/keys/by-id/{key_id}/quota-ledger")
async def list_key_quota_ledger_endpoint(
    key_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    pg_pool=Depends(get_pg),
):
    data = await list_key_quota_ledger_service(
        pg_pool,
        key_id=key_id,
        limit=limit,
        offset=offset,
    )

    return {
        "object": "list",
        "data": data,
        "limit": limit,
        "offset": offset,
    }