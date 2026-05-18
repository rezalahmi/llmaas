from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.schemas.file_search import FileSearchQuery, FileSearchResponse
from app.services.file_search import search_in_vector_store

router = APIRouter(prefix="/file_search", tags=["file_search"])


@router.post("/query", response_model=FileSearchResponse)
async def file_search_query(
    body: FileSearchQuery,
    current_user=Depends(get_current_user),
):
    # اگر بخواهی: چک کن user به این vector_store_ids دسترسی دارد
    # (مثلاً از Redis: user_vector_stores:{user_id})
    result = await search_in_vector_store(body)
    return result
