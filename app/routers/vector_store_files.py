# app\routers\vector_store_files.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status

import asyncio
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
from app.services.vector_store_file_service import attach_file_to_vector_store
from app.services.detach_file_service import detach_file_from_vector_store
from app.dependencies import get_current_user
from app.redis_client import get_redis

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
    r=Depends(get_redis)
):
    user_id = user.get("user_id")
    file_id = payload.file_id

    # ۱. اعتبارسنجی مالکیت فایل (Security Check)
    # بررسی می‌کنیم که آیا این فایل در لیست فایل‌های این کاربر هست یا خیر
    is_owner = await r.sismember(f"user_files:{user_id}", file_id)
    if not is_owner:
        logger.warning(f"Unauthorized access attempt: User {user_id} tried to access file {file_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file or the file does not exist."
        )

    # ۲. بررسی وجود متادیتای فایل در ردیس
    file_exists = await r.exists(f"file:{file_id}")
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File metadata not found. Please re-upload the file."
        )


    try:
        # ۴. اجرای عملیات اصلی (Ingestion)
        # نکته: اگر این پروسه خیلی طولانی است، باید از BackgroundTasks یا Celery استفاده کرد.
        logger.info(f"Starting ingestion for file {file_id} into VS {vector_store_id}")
        
        result = await attach_file_to_vector_store(
            redis=r,
            vector_store_id=vector_store_id,
            file_id=file_id,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap
        )

        # # ۵. ثبت موفقیت آمیز در ردیس (برای ردیابی‌های بعدی)
        # await r.sadd(f"vector_store_files:{vector_store_id}", vs_file_id)

        
        logger.info(f"Successfully attached file {file_id} to VS {vector_store_id}")
        return VectorStoreFileResponse(**result)

    except ValueError as ve:
        # خطاهای منطقی (مثلاً فرمت فایل نامعتبر برای چانکینگ)
        logger.error(f"Validation error during ingestion: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    
    except FileNotFoundError as e:
        logger.error(f"Ingestion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail="The file could not be processed because the source file is missing from the server storage."
        )


    except ConnectionError:
        # خطای اتصال به ChromaDB یا سرویس Embedding
        logger.error("External service connection failed during ingestion")
        raise HTTPException(
            status_code=503, 
            detail="Ingestion service is temporarily unavailable. Please try again later."
        )

    except Exception as e:
        # خطاهای غیرمنتظره
        logger.error(f"Unexpected error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An error occurred during the file processing/embedding phase."
        )
    


    
@router.post("/{vector_store_id}/file_batches", response_model=VectorStoreFileBatchResponse)
async def create_file_batch(
    vector_store_id: str,
    payload: VectorStoreFileBatchCreate,
    user=Depends(get_current_user),
    r=Depends(get_redis),
):
    user_id = user.get("user_id")
    
    # تعیین پارامترهای chunking (اگر در payload نبود از پیش‌فرض استفاده کن)
    chunk_size = payload.chunking.chunk_size if payload.chunking else 800
    chunk_overlap = payload.chunking.chunk_overlap if payload.chunking else 400

    # محدودیت تعداد فایل برای جلوگیری از فشار ناگهانی
    if len(payload.file_ids) > 100: 
        raise HTTPException(status_code=400, detail="Batch limit is 100 files.")

    # کنترل همزمانی (اجرای همزمان ۲ فایل برای جلوگیری از بلاک شدن CPU)
    sem = asyncio.Semaphore(2)

    async def process_file(file_id: str):
        async with sem:
            try:
                # چک کردن مالکیت فایل (همان منطق سرویس شما)
                if not await r.sismember(f"user_files:{user_id}", file_id):
                    return {"file_id": file_id, "status": "failed", "error": "Access denied"}
                
                # فراخوانی سرویس اصلی شما
                data = await attach_file_to_vector_store(
                    redis=r,
                    vector_store_id=vector_store_id,
                    file_id=file_id,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                return {"file_id": file_id, "status": "completed", "result": data}
            
            except Exception as e:
                return {"file_id": file_id, "status": "failed", "error": str(e)}

    # اجرای موازی
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
    redis=Depends(get_redis)
):

    try:

        result = await detach_file_from_vector_store(
            redis=redis,
            vector_store_id=vector_store_id,
            file_id=file_id,
            delete_file=req.delete_file
        )

        return result

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not attached to this vector store"
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not detach file"
        )