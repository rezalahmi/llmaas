# app\routers\files.py
import logging
import time
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from app.schemas.files import FileUploadResponse, FileListResponse
from app.dependencies import get_current_user
from app.services.file_service import save_file_stream
from app.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    r = Depends(get_redis)
):
    user_id = user.get("user_id")
    file_meta = None
    
    # ۱. اعتبارسنجی اولیه فایل
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")

    try:
        # ۲. ذخیره فایل در دیسک یا S3
        try:
            file_meta = await save_file_stream(file)
        except Exception as e:
            logger.error(f"Disk I/O Error during file upload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save file to storage."
            )

        # ۳. ثبت در ردیس (با مدیریت خطا)
        try:
            file_id = file_meta["id"]
            user_files_key = f"user_files:{user_id}"
            file_detail_key = f"file:{file_id}"

            # استفاده از Pipeline برای افزایش سرعت و پایداری (اختیاری اما توصیه شده)
            async with r.pipeline(transaction=True) as pipe:
                # افزودن آیدی فایل به لیست فایل‌های کاربر
                await pipe.sadd(user_files_key, file_id)
                
                # ذخیره جزئیات فایل به صورت Hash
                await pipe.hset(
                    file_detail_key,
                    mapping={
                        "user_id": user_id,
                        "filename": file_meta["filename"],
                        "bytes": str(file_meta["bytes"]), # در هش بهتر است رشته ذخیره شود
                        "path": file_meta["path"],
                        "created_at": int(time.time())
                    }
                )
                
                # به‌روزرسانی حجم مصرفی کاربر
                await pipe.incrby(f"user_storage:{user_id}", file_meta["bytes"])
                
                await pipe.execute()

        except Exception as e:
            logger.error(f"Redis Error for user {user_id}: {str(e)}")
            # در اینجا بهتر است اگر ثبت در دیتابیس شکست خورد، فایل ذخیره شده را پاک کنیم
            # os.remove(file_meta["path"]) 
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database error while registering file metadata."
            )

        return FileUploadResponse(
            file_id=file_meta["id"],
            filename=file_meta["filename"],
            bytes=file_meta["bytes"]
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.get("/", response_model=FileListResponse)
async def list_user_files(user=Depends(get_current_user), r = Depends(get_redis)):
    user_id = user.get("user_id")
    user_files_key = f"user_files:{user_id}"
    
    try:
        # ۱. دریافت آیدی تمام فایل‌های کاربر
        file_ids = await r.smembers(user_files_key)
        
        files = []
        for fid in file_ids:
            # تبدیل بایت به رشته (ردیس معمولاً بایت برمی‌گرداند)
            if isinstance(fid, bytes):
                fid = fid.decode('utf-8')

            # ۲. اصلاح روش خواندن: چون با hset ذخیره شده، باید با hgetall خوانده شود
            meta = await r.hgetall(f"file:{fid}")
            
            if meta:
                # تبدیل بایت‌های دیکشنری به رشته/عدد
                if "filename" in meta:
                    filename = meta.get("filename", "Unknown")
                    bytes_size = int(meta.get("bytes", 0))
                else:
                    # اگر redis bytes برگرداند
                    filename = meta.get(b"filename", b"Unknown").decode()
                    bytes_size = int(meta.get(b"bytes", b"0"))

                files.append({
                    "file_id": fid,
                    "filename": filename,
                    "bytes": bytes_size
                })
            else:
                # اگر آیدی در لیست بود ولی متادیتا نداشت (دیتای کثیف)
                logger.warning(f"File metadata missing for ID: {fid}")
                continue

        return FileListResponse(files=files)

    except Exception as e:
        logger.error(f"Error listing files for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve file list from database."
        )
