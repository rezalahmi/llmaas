import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.postgres_client import get_pg
from app.schemas.file_search import FileSearchQuery, FileSearchResponse
from app.services.file_search import search_in_vector_store
from app.utility.chroma_filters import map_query_filters_to_chroma
from app.services.vector_store_service import get_vector_stores_for_owner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/file_search", tags=["file_search"])


@router.post("/query", response_model=FileSearchResponse)
async def file_search_query(
    body: FileSearchQuery,
    current_user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    if not body.vector_store_ids:
        raise HTTPException(status_code=400, detail="At least one vector_store_id must be provided.")

    if not body.query or len(body.query.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search query is too short or empty.")

    api_key_id = current_user.get("id")
    if not api_key_id:
        raise HTTPException(status_code=401, detail="Invalid authentication context.")

    chroma_filters = None
    if body.filters:
        try:
            chroma_filters = map_query_filters_to_chroma(body.filters)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Unexpected error mapping filters: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail="Invalid filter format.")

    try:
        # فقط vector_store هایی که متعلق به همین api_key هستند را بگیر
        owned_vector_stores = await get_vector_stores_for_owner(
            pg=pg,
            api_key_id=api_key_id,
            vector_store_ids=body.vector_store_ids,
        )

        allowed_vs_ids = [row["id"] for row in owned_vector_stores]

        if not allowed_vs_ids:
            raise HTTPException(status_code=404, detail="No accessible vector stores found.")

        unauthorized_ids = set(body.vector_store_ids) - set(allowed_vs_ids)
        if unauthorized_ids:
            logger.warning(
                f"User api_key_id={api_key_id} attempted access to unauthorized vector stores: {list(unauthorized_ids)}"
            )

        search_request = FileSearchQuery(
            vector_store_ids=allowed_vs_ids,
            query=body.query,
            max_results=body.max_results,
            filters=chroma_filters
        )

        response = await search_in_vector_store(query=search_request)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error in file_search_query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the search process."
        )
