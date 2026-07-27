import hashlib
import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


DEFAULT_TTL_DAYS = 30


@dataclass(frozen=True)
class IdempotencyClaim:
    api_key_id: int
    operation: str
    key: str
    request_hash: str


def canonical_json_hash(
    *,
    method: str,
    route: str,
    payload: Any,
    api_key_id: int,
) -> str:
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    value = "\n".join(
        (method.upper(), route, canonical_payload, str(api_key_id))
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def multipart_hash(
    *,
    filename: str,
    content_type: str | None,
    file_sha256: str,
    api_key_id: int,
) -> str:
    value = "\n".join(
        (filename, content_type or "", file_sha256, str(api_key_id))
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _error_response(code: str, message: str, *, retry_after: int | None = None):
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        headers=headers,
        content={"error": {"code": code, "message": message}},
    )


async def claim_idempotency(
    pg,
    *,
    api_key_id: int,
    operation: str,
    key: str | None,
    request_hash: str,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> IdempotencyClaim | JSONResponse | None:
    if key is None:
        return None

    key = key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key cannot be empty.",
        )
    if len(key) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key cannot exceed 255 characters.",
        )

    row = await pg.fetchrow(
        """
        INSERT INTO idempotency_records (
            api_key_id,
            idempotency_key,
            operation,
            request_hash,
            status,
            expires_at
        )
        VALUES ($1, $2, $3, $4, 'started', NOW() + ($5 * INTERVAL '1 day'))
        ON CONFLICT (api_key_id, operation, idempotency_key)
        DO UPDATE SET
            request_hash = EXCLUDED.request_hash,
            status = 'started',
            response_status = NULL,
            response_body = NULL,
            resource_type = NULL,
            resource_id = NULL,
            created_at = NOW(),
            updated_at = NOW(),
            expires_at = EXCLUDED.expires_at
        WHERE idempotency_records.expires_at <= NOW()
        RETURNING status, response_status, response_body, request_hash
        """,
        api_key_id,
        key,
        operation,
        request_hash,
        ttl_days,
    )

    if row is not None:
        return IdempotencyClaim(api_key_id, operation, key, request_hash)

    row = await pg.fetchrow(
        """
        SELECT status, response_status, response_body, request_hash
        FROM idempotency_records
        WHERE api_key_id = $1
          AND operation = $2
          AND idempotency_key = $3
        """,
        api_key_id,
        operation,
        key,
    )

    if row["request_hash"] != request_hash:
        return _error_response(
            "idempotency_key_reused",
            "Idempotency-Key was already used with a different request",
        )

    if row["status"] in ("completed", "failed_terminal"):
        response_body = row["response_body"]
        if isinstance(response_body, str):
            response_body = json.loads(response_body)
        return JSONResponse(
            status_code=row["response_status"],
            content=response_body,
        )

    return _error_response(
        "idempotency_request_in_progress",
        "A request with this Idempotency-Key is already in progress",
        retry_after=2,
    )


async def complete_idempotency(
    pg,
    claim: IdempotencyClaim | None,
    *,
    response_status: int,
    response_body: dict[str, Any],
    resource_type: str,
    resource_id: str,
) -> None:
    if claim is None:
        return

    await pg.execute(
        """
        UPDATE idempotency_records
        SET status = 'completed',
            response_status = $5,
            response_body = $6::jsonb,
            resource_type = $7,
            resource_id = $8,
            updated_at = NOW()
        WHERE api_key_id = $1
          AND operation = $2
          AND idempotency_key = $3
          AND request_hash = $4
          AND status = 'started'
        """,
        claim.api_key_id,
        claim.operation,
        claim.key,
        claim.request_hash,
        response_status,
        json.dumps(response_body),
        resource_type,
        resource_id,
    )
