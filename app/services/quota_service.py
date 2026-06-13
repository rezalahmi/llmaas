from fastapi import HTTPException

from app.repositories.quota_repository import (
    credit_key_quota,
    consume_key_quota,
    get_user_quota_summary,
    list_key_quota_ledger,
)


async def credit_api_key_service(
    conn,
    *,
    key_id: int,
    amount: int,
    reason: str | None = None,
    reference_id: str | None = None,
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero")

    try:
        result = await credit_key_quota(
            conn,
            key_id=key_id,
            amount=amount,
            reason=reason,
            reference_id=reference_id,
        )
    except Exception:
        # اگر بعداً خواستی duplicate reference_id را هندل کنی،
        # اینجا می‌توانی روی UniqueViolationError شرط بگذاری.
        raise

    if not result:
        raise HTTPException(status_code=404, detail="active api key not found")

    return result


async def consume_api_key_quota_service(
    conn,
    *,
    key_id: int,
    amount: int,
    reason: str | None = None,
    reference_id: str | None = None,
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero")

    result = await consume_key_quota(
        conn,
        key_id=key_id,
        amount=amount,
        reason=reason,
        reference_id=reference_id,
    )

    if not result:
        raise HTTPException(status_code=402, detail="insufficient quota or inactive api key")

    return result


async def get_key_quota_service(conn, *, key_id: int):
    row = await conn.fetchrow(
        """
        SELECT
            id,
            external_user_id,
            quota,
            is_active
        FROM api_keys
        WHERE id = $1
        """,
        key_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "key_id": row["id"],
        "external_user_id": row["external_user_id"],
        "quota_remaining": int(row["quota"] or 0),
        "is_active": bool(row["is_active"]),
    }


async def get_user_quota_summary_service(conn, *, external_user_id: int):
    return await get_user_quota_summary(conn, external_user_id=external_user_id)


async def list_key_quota_ledger_service(
    conn,
    *,
    key_id: int,
    limit: int = 50,
    offset: int = 0,
):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    return await list_key_quota_ledger(
        conn,
        key_id=key_id,
        limit=limit,
        offset=offset,
    )
