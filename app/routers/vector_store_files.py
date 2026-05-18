from fastapi import APIRouter, Depends
from app.schemas.vector_store_files import (
    VectorStoreFileCreate,
    VectorStoreFileResponse
)
from app.services.vector_store_file_service import attach_file_to_vector_store
from app.dependencies import get_current_user
from app.redis_client import get_redis


router = APIRouter(
    prefix="/vector_stores",
    tags=["Vector Store Files"]
)


@router.post("/{vector_store_id}/files", response_model=VectorStoreFileResponse)
async def attach_file(
    vector_store_id: str,
    payload: VectorStoreFileCreate,
    user=Depends(get_current_user),
    r=Depends(get_redis)
):

    result = await attach_file_to_vector_store(
        redis=r,
        vector_store_id=vector_store_id,
        file_id=payload.file_id,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap
    )

    return VectorStoreFileResponse(**result)
