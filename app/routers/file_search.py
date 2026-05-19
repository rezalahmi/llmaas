import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_user
from app.schemas.file_search import FileSearchQuery, FileSearchResponse
from app.services.file_search import search_in_vector_store
from app.utility.chroma_filters import map_query_filters_to_chroma

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/file_search", tags=["file_search"])

@router.post("/query", response_model=FileSearchResponse)
async def file_search_query(
    body: FileSearchQuery,
    current_user=Depends(get_current_user),
):
    # ۱. اعتبارسنجی اولیه (Input Validation)
    if not body.vector_store_ids:
        raise HTTPException(status_code=400, detail="At least one vector_store_id must be provided.")
    
    if not body.query or len(body.query.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search query is too short or empty.")

    # ۲. تبدیل فیلترها با مدیریت خطای دقیق
    chroma_filters = None
    if body.filters:
        try:
            chroma_filters = map_query_filters_to_chroma(body.filters)
        except ValueError as ve:
            # خطای بیزینسی در فرمت فیلتر
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Unexpected error mapping filters: {e}")
            raise HTTPException(status_code=400, detail="Invalid filter format.")

    # ۳. فراخوانی سرویس
    try:
        search_request = FileSearchQuery(
            vector_store_ids=body.vector_store_ids,
            query=body.query,
            max_results=body.max_results,
            filters=chroma_filters
        )
        
        response = await search_in_vector_store(query=search_request)
        return response

    except HTTPException as he:
        # خطاهایی که خود سرویس شناسایی کرده (مثل ۵۰۲ یا ۵۰۳) را مستقیماً برمی‌گردانیم
        raise he
    except Exception as e:
        # خطاهای پیش‌بینی نشده (Internal Server Error)
        logger.error(f"Critical error in file_search_query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the search process."
        )
