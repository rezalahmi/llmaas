import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.vector_stores import (
    VectorStoreCreate,
    VectorStoreResponse,
    VectorStoreDeletedResponse,
    VectorStoreFileListResponse,
)

from app.dependencies import get_current_user
from app.postgres_client import get_pg

from app.services.vector_store_service import (
    create_chroma_collection,
    delete_chroma_collection,
)

from app.services.vector_store_metadata_service import (
    generate_vector_store_id,
    create_vector_store_record,
    mark_vector_store_failed,
    count_user_vector_stores,
    list_vector_stores_by_api_key,
    get_vector_store_for_owner,
    soft_delete_vector_store,
    soft_delete_vector_store_files,
    list_vector_store_files_by_owner,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vector_stores", tags=["Vector Stores"])


@router.post("/", response_model=VectorStoreResponse)
async def create_vs(
    payload: VectorStoreCreate,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    external_user_id = user.get("external_user_id")
    api_key_id = user.get("id")

    if api_key_id is None:
        api_key_id = user.get("api_key_id")

    name = payload.name.strip() if payload.name else None

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vector store name cannot be empty."
        )

    existing_count = await count_user_vector_stores(pg, api_key_id=api_key_id)

    if existing_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have reached the maximum limit of 10 vector stores."
        )

    vector_store_id = generate_vector_store_id()
    collection_name = vector_store_id

    try:
        create_chroma_collection(collection_name)

        row = await create_vector_store_record(
            pg,
            vector_store_id=vector_store_id,
            external_user_id=external_user_id,
            api_key_id=api_key_id,
            name=name,
            collection_name=collection_name,
        )

        logger.info(
            f"User api_key_id={api_key_id} created vector store {vector_store_id}"
        )

        return VectorStoreResponse(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to create vector store: {str(e)}", exc_info=True)

        try:
            delete_chroma_collection(collection_name)
        except Exception:
            pass

        try:
            await mark_vector_store_failed(
                pg,
                vector_store_id=vector_store_id,
                error=str(e),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create vector store in the backend."
        )


@router.get("/", response_model=list[VectorStoreResponse])
async def list_vector_stores(
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user.get("id")

    if api_key_id is None:
        api_key_id = user.get("api_key_id")

    rows = await list_vector_stores_by_api_key(
        pg,
        api_key_id=api_key_id,
    )

    return [
        VectorStoreResponse(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.delete(
    "/{vector_store_id}",
    response_model=VectorStoreDeletedResponse,
)
async def remove_vector_store(
    vector_store_id: str,
    delete_files: bool = False,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user.get("id")

    if api_key_id is None:
        api_key_id = user.get("api_key_id")

    row = await get_vector_store_for_owner(
        pg,
        vector_store_id=vector_store_id,
        api_key_id=api_key_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vector store not found or you don't have permission to delete it."
        )

    collection_name = row["collection_name"]

    try:
        delete_chroma_collection(collection_name)

        await soft_delete_vector_store_files(
            pg,
            vector_store_id=vector_store_id,
        )

        deleted_row = await soft_delete_vector_store(
            pg,
            vector_store_id=vector_store_id,
            api_key_id=api_key_id,
        )

        if not deleted_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector store not found or already deleted."
            )

        # فعلاً delete_files را اینجا انجام نمی‌دهیم، چون فایل‌ها از جدول files مدیریت می‌شوند.
        # اگر خواستی در آینده delete_files=True واقعاً فایل‌ها را هم soft delete کند،
        # باید با files service وصلش کنیم.

        return VectorStoreDeletedResponse(
            id=vector_store_id,
            object="vector_store.deleted",
            deleted=True,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to delete vector store: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete vector store"
        )


@router.get(
    "/{vector_store_id}/files",
    response_model=VectorStoreFileListResponse,
)
async def list_files_in_vector_store(
    vector_store_id: str,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user.get("id")

    if api_key_id is None:
        api_key_id = user.get("api_key_id")

    vs = await get_vector_store_for_owner(
        pg,
        vector_store_id=vector_store_id,
        api_key_id=api_key_id,
    )

    if not vs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vector store not found or you don't have permission to access it."
        )

    rows = await list_vector_store_files_by_owner(
        pg,
        vector_store_id=vector_store_id,
        api_key_id=api_key_id,
    )

    items = [
        {
            "id": row["file_id"],
            "object": "vector_store.file",
            "created_at": row["created_at"],
            "vector_store_id": row["vector_store_id"],
        }
        for row in rows
    ]

    return {
        "object": "list",
        "data": items,
        "first_id": items[0]["id"] if items else None,
        "last_id": items[-1]["id"] if items else None,
        "has_more": False,
    }



#TODO     GET /vector_stores/{vs_id}

#TODO     POST /vector_stores/{vs_id}  # یا PATCH
