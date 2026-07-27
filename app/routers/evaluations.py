import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.dependencies import get_current_user
from app.postgres_client import get_pg
from app.repositories.evaluation_repository import (
    create_dataset,
    create_evaluation_run,
    generate_dataset_id,
    generate_run_id,
    get_dataset_for_owner,
    get_evaluation_run_for_owner,
    list_evaluation_results,
)
from app.schemas.evaluations import (
    EvaluationDatasetCreate,
    EvaluationDatasetResponse,
    EvaluationResultList,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from app.services.idempotency_service import (
    IdempotencyClaim,
    canonical_json_hash,
    claim_idempotency,
    complete_idempotency,
)
from app.services.semantic_coverage_service import EVALUATOR_VERSION
from app.services.vector_store_metadata_service import get_vector_store_for_owner
from app.tasks import semantic_coverage_evaluation_task


router = APIRouter(
    prefix="/vector_stores",
    tags=["Vector Store Evaluations"],
)


def _json_object(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _unix(value) -> int | None:
    return int(value.timestamp()) if value is not None else None


def _dataset_response(row) -> EvaluationDatasetResponse:
    return EvaluationDatasetResponse(
        id=row["id"],
        vector_store_id=row["vector_store_id"],
        name=row["name"],
        version=row["version"],
        status=row["status"],
        case_count=row["case_count"],
        created_at=_unix(row["created_at"]),
    )


def _run_response(row) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        id=row["id"],
        vector_store_id=row["vector_store_id"],
        dataset_id=row["dataset_id"],
        type=row["type"],
        status=row["status"],
        config=_json_object(row["config"]) or {},
        summary=_json_object(row["summary"]),
        evaluator_version=row["evaluator_version"],
        error=row["error"],
        created_at=_unix(row["created_at"]),
        started_at=_unix(row["started_at"]),
        completed_at=_unix(row["completed_at"]),
    )


async def _require_vector_store(pg, *, vector_store_id: str, api_key_id: int):
    vector_store = await get_vector_store_for_owner(
        pg,
        vector_store_id=vector_store_id,
        api_key_id=api_key_id,
    )
    if not vector_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vector store not found.",
        )
    return vector_store


@router.post(
    "/{vector_store_id}/evaluation_datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_dataset(
    vector_store_id: str,
    payload: EvaluationDatasetCreate,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user["id"]
    await _require_vector_store(
        pg, vector_store_id=vector_store_id, api_key_id=api_key_id
    )

    try:
        row = await create_dataset(
            pg,
            dataset_id=generate_dataset_id(),
            api_key_id=api_key_id,
            vector_store_id=vector_store_id,
            name=payload.name,
            version=payload.version,
            cases=[
                case.model_dump(mode="json")
                for case in payload.cases
            ],
        )
    except Exception as exc:
        if getattr(exc, "sqlstate", None) == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A dataset with this name and version already exists.",
            ) from exc
        raise

    return _dataset_response(row)


@router.get(
    "/{vector_store_id}/evaluation_datasets/{dataset_id}",
    response_model=EvaluationDatasetResponse,
)
async def get_evaluation_dataset(
    vector_store_id: str,
    dataset_id: str,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    row = await get_dataset_for_owner(
        pg,
        dataset_id=dataset_id,
        vector_store_id=vector_store_id,
        api_key_id=user["id"],
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation dataset not found.",
        )
    return _dataset_response(row)


@router.post(
    "/{vector_store_id}/evaluations",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_vector_store_evaluation(
    vector_store_id: str,
    payload: EvaluationRunCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user["id"]
    await _require_vector_store(
        pg, vector_store_id=vector_store_id, api_key_id=api_key_id
    )
    dataset = await get_dataset_for_owner(
        pg,
        dataset_id=payload.dataset_id,
        vector_store_id=vector_store_id,
        api_key_id=api_key_id,
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation dataset not found.",
        )

    request_body = payload.model_dump(mode="json")
    idempotency = await claim_idempotency(
        pg,
        api_key_id=api_key_id,
        operation="create_vector_store_evaluation",
        key=idempotency_key,
        request_hash=canonical_json_hash(
            method="POST",
            route=f"/vector_stores/{vector_store_id}/evaluations",
            payload=request_body,
            api_key_id=api_key_id,
        ),
    )
    if idempotency is not None and not isinstance(
        idempotency, IdempotencyClaim
    ):
        return idempotency

    row = await create_evaluation_run(
        pg,
        run_id=generate_run_id(),
        api_key_id=api_key_id,
        vector_store_id=vector_store_id,
        dataset_id=payload.dataset_id,
        evaluation_type=payload.type,
        config=payload.config.model_dump(mode="json"),
        evaluator_version=EVALUATOR_VERSION,
    )
    response = _run_response(row)

    try:
        semantic_coverage_evaluation_task.delay(row["id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue the evaluation job.",
        ) from exc

    await complete_idempotency(
        pg,
        idempotency,
        response_status=status.HTTP_202_ACCEPTED,
        response_body=response.model_dump(mode="json"),
        resource_type="vector_store_evaluation",
        resource_id=row["id"],
    )
    return response


@router.get(
    "/{vector_store_id}/evaluations/{evaluation_id}",
    response_model=EvaluationRunResponse,
)
async def get_vector_store_evaluation(
    vector_store_id: str,
    evaluation_id: str,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    row = await get_evaluation_run_for_owner(
        pg,
        run_id=evaluation_id,
        vector_store_id=vector_store_id,
        api_key_id=user["id"],
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found.",
        )
    return _run_response(row)


@router.get(
    "/{vector_store_id}/evaluations/{evaluation_id}/results",
    response_model=EvaluationResultList,
)
async def get_vector_store_evaluation_results(
    vector_store_id: str,
    evaluation_id: str,
    after: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    run = await get_evaluation_run_for_owner(
        pg,
        run_id=evaluation_id,
        vector_store_id=vector_store_id,
        api_key_id=user["id"],
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found.",
        )

    rows = await list_evaluation_results(
        pg,
        run_id=evaluation_id,
        after=after,
        limit=limit,
    )
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    data = [
        {
            "id": row["id"],
            "case_id": row["case_id"],
            "metric": row["metric"],
            "score": row["score"],
            "severity": row["severity"],
            "details": _json_object(row["details"]) or {},
            "created_at": _unix(row["created_at"]),
        }
        for row in visible_rows
    ]
    return {
        "object": "list",
        "data": data,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
        "has_more": has_more,
    }
