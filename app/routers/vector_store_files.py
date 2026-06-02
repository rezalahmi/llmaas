# app\routers\vector_store_files.py
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.vector_store_files import (
    VectorStoreFileCreate,
    VectorStoreFileResponse,
    VectorStoreFileDetachRequest,
    VectorStoreFileDetachResponse
)
from app.schemas.vector_store_batch_files import (
    VectorStoreFileBatchCreate,
    VectorStoreFileBatchResponse,
)

from app.postgres_client import get_pool 

# سرویس‌های جدید که باید بسازیم یا اصلاح کنیم
from app.services.vector_store_file_service import attach_file_to_vector_store, detach_file_from_vector_store_pg
from app.services.vector_store_metadata_service import (
    get_vector_store_for_owner,
    attach_file_to_vector_store as db_attach_file
)
from app.services.file_metadata_service import get_file_metadata 

from app.dependencies import get_current_user
from app.postgres_client import get_pg

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vector_stores",
    tags=["Vector Store Files"]
)

@router.post("/{vector_store_id}/files", response_model=VectorStoreFileResponse)
async def attach_file(
    vector_store_id: str,
    payload: VectorStoreFileCreate,
    user=Depends(get_current_user),
    pg=Depends(get_pg)
):
    api_key_id = user.get("id")
    external_user_id = user.get("external_user_id")
    file_id = payload.file_id

    # ۱. بررسی وجود و مالکیت Vector Store
    vs = await get_vector_store_for_owner(pg, vector_store_id=vector_store_id, api_key_id=api_key_id)
    if not vs:
        raise HTTPException(status_code=404, detail="Vector store not found.")

    # ۲. بررسی وجود و مالکیت فایل در Postgres
    file_record = await get_file_metadata(pg, file_id) # مطمئن شو این تابع api_key_id را هم چک می‌کند
    if not file_record or file_record["api_key_id"] != api_key_id:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file or the file does not exist."
        )

    if file_record["status"] != "ready":
        raise HTTPException(status_code=400, detail="File is not ready for processing.")

    try:
        # ۳. ثبت در دیتابیس (وضعیت در حال پردازش)
        await db_attach_file(
            pg, 
            vector_store_id=vector_store_id, 
            file_id=file_id, 
            external_user_id=external_user_id, 
            api_key_id=api_key_id,
            status="processing"
        )

        # ۴. اجرای عملیات Ingestion (استخراج متن و Chroma)
        # نکته: در آینده این بخش باید برود در BackgroundTask
        result = await attach_file_to_vector_store(
            pg=pg,
            vector_store_id=vector_store_id,
            file_id=file_id,
            file_record=file_record,
            chunk_size=payload.chunk_size or 800,
            chunk_overlap=payload.chunk_overlap or 400
        )

        return VectorStoreFileResponse(**result)

    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {str(e)}", exc_info=True)
        # آپدیت وضعیت به failed در دیتابیس (اختیاری)
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred: {str(e)}"
        )
    
@router.post("/{vector_store_id}/file_batches", response_model=VectorStoreFileBatchResponse)
async def create_file_batch(
    vector_store_id: str,
    payload: VectorStoreFileBatchCreate,
    user=Depends(get_current_user),
    pool=Depends(get_pool),
):
    api_key_id = user.get("id")

    # بررسی اولیه با یک کانکشن که از Pool می‌گیرید
    async with pool.acquire() as conn:
        vs = await get_vector_store_for_owner(conn, vector_store_id=vector_store_id, api_key_id=api_key_id)
        if not vs:
            raise HTTPException(status_code=404, detail="Vector store not found.")

    sem = asyncio.Semaphore(2)

    async def process_file(file_id: str):
        async with sem:
            # هر تسک، کانکشنِ اختصاصی خودش را از Pool می‌گیرد
            async with pool.acquire() as conn:
                try:
                    file_record = await get_file_metadata(conn, file_id)
                    if not file_record:
                        return {"file_id": file_id, "status": "failed", "error": "File not found"}
                    
                    if file_record.get("api_key_id") != api_key_id:
                        return {"file_id": file_id, "status": "failed", "error": "Access denied"}

                    # پردازش اصلی
                    data = await attach_file_to_vector_store(
                        pg=conn,  # کانکشن اختصاصی این تسک
                        vector_store_id=vector_store_id,
                        file_id=file_id,
                        file_record=file_record,
                        chunk_size=payload.chunking.chunk_size,
                        chunk_overlap=payload.chunking.chunk_overlap
                    )
                    return {"file_id": file_id, "status": "completed", "result": data}
                
                except Exception as e:
                    logger.error(f"Batch ingestion failed for {file_id}: {e}", exc_info=True)
                    return {"file_id": file_id, "status": "failed", "error": str(e)}

    tasks = [process_file(fid) for fid in payload.file_ids]
    results = await asyncio.gather(*tasks)

    return {
        "vector_store_id": vector_store_id,
        "status": "completed",
        "file_results": results
    }



@router.delete(
    "/{vector_store_id}/files/{file_id}",
    response_model=VectorStoreFileDetachResponse
)
async def detach_file(
    vector_store_id: str,
    file_id: str,
    req: VectorStoreFileDetachRequest,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    api_key_id = user.get("id")

    try:
        result = await detach_file_from_vector_store_pg(
            pg=pg,
            vector_store_id=vector_store_id,
            file_id=file_id,
            api_key_id=api_key_id,
            delete_file=req.delete_file
        )
        return result

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not attached to this vector store"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Could not detach file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not detach file"
        )