from fastapi import APIRouter, Depends
from app.schemas.vector_stores import VectorStoreCreate, VectorStoreResponse
from app.services.vector_store_service import create_vector_store
from app.dependencies import get_current_user
from app.redis_client import get_redis

router = APIRouter(prefix="/vector_stores", tags=["Vector Stores"])


@router.post("/", response_model=VectorStoreResponse)
async def create_vs(
    payload: VectorStoreCreate,
    user=Depends(get_current_user),
    r=Depends(get_redis)
):
    vs = await create_vector_store(
        r,
        user_id=user["user_id"],
        name=payload.name
    )

    return VectorStoreResponse(
        id=vs["id"],
        name=vs["name"],
        created_at=vs["created_at"]
    )
