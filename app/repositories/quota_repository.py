# app/repositories/quota_repository.py

from typing import Optional


async def credit_key_quota(
    conn,
    *,
    key_id: int,
    amount: int,
    reason: Optional[str] = None,
    reference_id: Optional[str] = None,
):
    """
    افزایش اعتبار یک API Key.
    amount باید مثبت باشد.
    """

    async with conn.transaction():
        key_row = await conn.fetchrow(
            """
            UPDATE api_keys
            SET quota = quota + $1
            WHERE id = $2
              AND is_active = true
            RETURNING id, external_user_id, quota
            """,
            amount,
            key_id,
        )

        if not key_row:
            return None

        ledger_row = await conn.fetchrow(
            """
            INSERT INTO api_key_quota_ledger (
                api_key_id,
                external_user_id,
                amount,
                balance_after,
                type,
                reason,
                reference_id
            )
            VALUES ($1, $2, $3, $4, 'credit', $5, $6)
            RETURNING id
            """,
            key_row["id"],
            key_row["external_user_id"],
            amount,
            key_row["quota"],
            reason,
            reference_id,
        )

        return {
            "key_id": key_row["id"],
            "external_user_id": key_row["external_user_id"],
            "credited": amount,
            "quota_remaining": key_row["quota"],
            "ledger_id": ledger_row["id"],
        }


async def consume_key_quota(
    conn,
    *,
    key_id: int,
    amount: int,
    reason: Optional[str] = None,
    reference_id: Optional[str] = None,
):
    """
    کم کردن اعتبار از یک API Key به صورت Atomic.
    اگر اعتبار کافی نباشد، None برمی‌گرداند.
    """

    async with conn.transaction():
        key_row = await conn.fetchrow(
            """
            UPDATE api_keys
            SET quota = quota - $1,
                last_used_at = NOW()
            WHERE id = $2
              AND is_active = true
              AND quota >= $1
            RETURNING id, external_user_id, quota
            """,
            amount,
            key_id,
        )

        if not key_row:
            return None

        ledger_row = await conn.fetchrow(
            """
            INSERT INTO api_key_quota_ledger (
                api_key_id,
                external_user_id,
                amount,
                balance_after,
                type,
                reason,
                reference_id
            )
            VALUES ($1, $2, $3, $4, 'debit', $5, $6)
            RETURNING id
            """,
            key_row["id"],
            key_row["external_user_id"],
            -amount,
            key_row["quota"],
            reason,
            reference_id,
        )

        return {
            "key_id": key_row["id"],
            "external_user_id": key_row["external_user_id"],
            "debited": amount,
            "quota_remaining": key_row["quota"],
            "ledger_id": ledger_row["id"],
        }


async def get_key_quota(conn, *, key_id: int):
    row = await conn.fetchrow(
        """
        SELECT
            id,
            external_user_id,
            user_name,
            key_prefix,
            quota,
            is_active,
            created_at,
            last_used_at
        FROM api_keys
        WHERE id = $1
        """,
        key_id,
    )

    if not row:
        return None

    return dict(row)


async def get_user_quota_summary(conn, *, external_user_id: int):
    row = await conn.fetchrow(
        """
        SELECT
            external_user_id,
            COUNT(*) AS total_keys,
            COUNT(*) FILTER (WHERE is_active = true) AS active_keys,
            COALESCE(SUM(quota), 0) AS total_quota_remaining
        FROM api_keys
        WHERE external_user_id = $1
        GROUP BY external_user_id
        """,
        external_user_id,
    )

    if not row:
        return {
            "external_user_id": external_user_id,
            "total_keys": 0,
            "active_keys": 0,
            "total_quota_remaining": 0,
        }

    return dict(row)


async def list_key_quota_ledger(
    conn,
    *,
    key_id: int,
    limit: int = 50,
    offset: int = 0,
):
    rows = await conn.fetch(
        """
        SELECT
            id,
            api_key_id,
            external_user_id,
            amount,
            balance_after,
            type,
            reason,
            reference_id,
            created_at
        FROM api_key_quota_ledger
        WHERE api_key_id = $1
        ORDER BY id DESC
        LIMIT $2 OFFSET $3
        """,
        key_id,
        limit,
        offset,
    )

    return [dict(r) for r in rows]
