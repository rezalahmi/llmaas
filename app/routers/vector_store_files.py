# app\routers\vector_store_files.py
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request

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
    attach_file_to_vector_store as db_attach_file,
    upsert_vector_store_file,
    get_vector_store_files_list
)
from app.services.file_metadata_service import get_file_metadata 
from app.services.vector_store_batch_service import create_batch_record, update_batch_progress, get_batch_status
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
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    pool=Depends(get_pool),
):
    api_key_id = user.get("id")
    external_user_id = user.get("external_user_id")

    # ۱. کارهای مقدماتی و ایجاد رکورد Batch
    async with pool.acquire() as conn:
        vs = await get_vector_store_for_owner(conn, vector_store_id=vector_store_id, api_key_id=api_key_id)
        if not vs:
            raise HTTPException(status_code=404, detail="Vector store not found.")
        
        # ساخت رکورد Batch در دیتابیس در همین مرحله
        batch_id = await create_batch_record(conn, vector_store_id, api_key_id, len(payload.file_ids))

    # ۲. تعریف تابع Ingestion (بهتر است خارج از روت باشد، اما اینجا برای دسترسی راحت اصلاحش می‌کنیم)
    # توجه: تمام متغیرهای مورد نیاز را صراحتاً به تابع پاس می‌دهیم
    async def run_batch_ingestion_task(
        target_pool, 
        vs_id: str, 
        b_id: str, 
        f_ids: list, 
        chunk_cfg, 
        u_id: int, 
        k_id: int
    ):
        sem = asyncio.Semaphore(2) # محدودیت برای جلوگیری از Overload

        async def process_single(file_id):
            async with sem:
                # برای هر فایل یک کانکشن تازه از استخر می‌گیریم
                async with target_pool.acquire() as conn:
                    try:
                        file_record = await get_file_metadata(conn, file_id)
                        if not file_record:
                            raise Exception(f"File {file_id} not found")

                        await attach_file_to_vector_store(
                            pg=conn,
                            vector_store_id=vs_id,
                            file_id=file_id,
                            file_record=file_record,
                            chunk_size=chunk_cfg.chunk_size,
                            chunk_overlap=chunk_cfg.chunk_overlap,
                            batch_id=b_id
                        )
                        await update_batch_progress(conn, b_id, success=True)
                    except Exception as e:
                        logger.error(f"Batch processing error for file {file_id}: {str(e)}")
                        # ثبت وضعیت شکست برای فایل
                        await upsert_vector_store_file(
                            conn, vs_id, file_id, u_id, k_id, 
                            status="failed", batch_id=b_id, error=str(e)
                        )
                        await update_batch_progress(conn, b_id, success=False)

        tasks = [process_single(fid) for fid in f_ids]
        await asyncio.gather(*tasks)

    # ۳. سپردن به Background Task
    background_tasks.add_task(
        run_batch_ingestion_task,
        pool,
        vector_store_id,
        batch_id,
        payload.file_ids,
        payload.chunking,
        external_user_id,
        api_key_id
    )

    # ۴. پاسخ فوری به کاربر
    return {
        "id": batch_id,
        "object": "vector_store.file_batch",
        "vector_store_id": vector_store_id,
        "status": "in_progress",
        "created_at": int(datetime.now(timezone.utc).timestamp())
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
    
@router.get("/{vector_store_id}/file_batches/{batch_id}")
async def get_batch(
    vector_store_id: str,
    batch_id: str,
    user=Depends(get_current_user),
    pg=Depends(get_pg)
):
    status = await get_batch_status(pg, batch_id, user.get("id"))
    if not status:
        raise HTTPException(status_code=404, detail="Batch not found")
    return status


@router.get("/{vector_store_id}/files")
async def list_vector_store_files(
    vector_store_id: str,
    limit: int = 20,
    after: str = None,
    user=Depends(get_current_user),
    pool=Depends(get_pool)
):
    api_key_id = user.get("id")
    
    async with pool.acquire() as conn:
        # ۱. بررسی دسترسی (هنوز در لایه سرویس است)
        vs = await get_vector_store_for_owner(conn, vector_store_id, api_key_id)
        if not vs:
            raise HTTPException(status_code=404, detail="Vector store not found.")

        # ۲. فراخوانی منطق از لایه سرویس
        rows = await get_vector_store_files_list(conn, vector_store_id, limit, after)
        
        # ۳. فرمت‌دهی خروجی دقیقاً مشابه OpenAI
        data = []
        for row in rows:
            status = "completed" if row["status"] == "ready" else row["status"]
            
            # مدیریت ساختار خطا مشابه OpenAI
            last_error = None
            if row["last_error"]:
                last_error = {
                    "code": "server_error",
                    "message": row["last_error"]
                }

            data.append({
                "id": row["file_id"], # OpenAI آی‌دی فایل را به عنوان ID رکورد برمی‌گرداند
                "object": "vector_store.file",
                "usage_bytes": row["usage_bytes"] or 0,
                "created_at": int(row["created_at"].timestamp()),
                "vector_store_id": row["vector_store_id"],
                "status": status,
                "last_error": last_error,
                "chunking_strategy": {
                    "type": "static",
                    "static": {
                        "max_chunk_size_tokens": 800, # مقادیر پیش‌فرض یا ذخیره شده
                        "chunk_overlap_tokens": 400
                    }
                },
                "attributes": {}
            })
            
        return {
            "object": "list",
            "data": data,
            "first_id": data[0]["id"] if data else None,
            "last_id": data[-1]["id"] if data else None,
            "has_more": len(data) == limit
        }



#TODO     POST /vector_stores/{vs_id}/file_batches/{batch_id}/cancel

#TODO     GET /vector_stores/{vs_id}/files