# app\routers\file_search.py
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from app.schemas.file_search import FileSearchQuery, FileSearchResponse
from app.services.file_search import search_in_vector_store
from app.utility.chroma_filters import map_query_filters_to_chroma



router = APIRouter(prefix="/file_search", tags=["file_search"])

# فرض می‌کنیم get_redis_client را داریم
@router.post("/query", response_model=FileSearchResponse)
async def file_search_query(
    body: FileSearchQuery,
    current_user=Depends(get_current_user), # در صورت نیاز برای چک کردن دسترسی
):
    # 1. Map user filters to ChromaDB format
    chroma_filters = None
    if body.filters:
        try:
            chroma_filters = map_query_filters_to_chroma(body.filters)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid filter format: {e}")

    # 2. Call the search service with filters
    try:
        search_query = FileSearchQuery(
            vector_store_ids=body.vector_store_ids,
            query=body.query,
            max_results=body.max_results,
            filters=chroma_filters # ارسال فیلترهای فرمت شده Chroma
        )
        # چون search_in_vector_store الان کل query object را می‌گیرد،
        # آن را مستقیماً پاس می‌دهیم.
        response = await search_in_vector_store(query=search_query)
        return response
    except Exception as e:
        # Log the error properly
        print(f"Error during file search: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during file search.")
