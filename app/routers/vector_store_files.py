# app\routers\vector_store_files.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.vector_store_files import (
    VectorStoreFileCreate,
    VectorStoreFileResponse
)
from app.services.vector_store_file_service import attach_file_to_vector_store
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

    # ۳. جلوگیری از پردازش تکراری (Idempotency - اختیاری اما مفید)
    # چک می‌کنیم آیا این فایل قبلاً به این Vector Store متصل شده؟
    # (این کار مستلزم این است که در سرویس، این رابطه را در ردیس ذخیره کرده باشید)
    is_already_attached = await r.sismember(f"vs_files:{vector_store_id}", file_id)
    if is_already_attached:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This file is already attached to the vector store."
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

        # ۵. ثبت موفقیت آمیز در ردیس (برای ردیابی‌های بعدی)
        await r.sadd(f"vs_files:{vector_store_id}", file_id)
        
        logger.info(f"Successfully attached file {file_id} to VS {vector_store_id}")
        return VectorStoreFileResponse(**result)

    except ValueError as ve:
        # خطاهای منطقی (مثلاً فرمت فایل نامعتبر برای چانکینگ)
        logger.error(f"Validation error during ingestion: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))

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
