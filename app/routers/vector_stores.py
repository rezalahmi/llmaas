# app\routers\vector_stores.py
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.vector_stores import VectorStoreCreate, VectorStoreResponse
from app.services.vector_store_service import create_vector_store
from app.dependencies import get_current_user
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vector_stores", tags=["Vector Stores"])

@router.post("/", response_model=VectorStoreResponse)
async def create_vs(
    payload: VectorStoreCreate,
    user=Depends(get_current_user),
    r=Depends(get_redis)
):
    user_id = user.get("user_id")
    
    # ۱. اعتبارسنجی ورودی
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vector store name cannot be empty."
        )

    try:
        # ۲. چک کردن محدودیت تعداد (Business Logic)
        # مثلاً هر کاربر حداکثر ۱۰ کالکشن داشته باشد
        user_vs_key = f"user_vs:{user_id}"
        existing_count = await r.scard(user_vs_key)
        if existing_count >= 10:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have reached the maximum limit of 10 vector stores."
            )

        # ۳. فراخوانی سرویس برای ایجاد کالکشن در Chroma و ثبت در Redis
        try:
            # سرویس داخلی باید هندل کند که اگر در Chroma ساخته شد اما در ردیس نشد، Rollback کند
            vs = await create_vector_store(
                r,
                user_id=user_id,
                name=name
            )
        except Exception as e:
            logger.error(f"Service Layer Error while creating VS: {str(e)}")
            # اگر خطای خاصی از سمت سرویس (مثل تکراری بودن نام در Chroma) بیاید:
            if "already exists" in str(e).lower():
                raise HTTPException(status_code=409, detail="A vector store with this ID already exists.")
            raise HTTPException(status_code=502, detail="Failed to create vector store in the backend.")

        # ۴. اطمینان از ثبت در لیست کالکشن‌های کاربر
        # این مرحله معمولاً داخل سرویس انجام می‌شود، اما برای اطمینان مجدد:
        await r.sadd(user_vs_key, vs["id"])

        logger.info(f"User {user_id} created a new vector store: {vs['id']} ({name})")
        
        return VectorStoreResponse(
            id=vs["id"],
            name=vs["name"],
            created_at=vs.get("created_at", int(time.time()))
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in create_vs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the vector store."
        )

# اضافه کردن متد List برای تکمیل Robustness
@router.get("/", response_model=list[VectorStoreResponse])
async def list_vector_stores(
    user=Depends(get_current_user),
    r=Depends(get_redis)
):
    user_id = user.get("user_id")
    user_vs_key = f"user_vs:{user_id}"
    logger.debug("START DEBUG list_vector_stores")

    if not await r.exists(user_vs_key):
        logger.warning(f"No vector store key found for user: {user_vs_key}")
        return []
    
    try:
        vs_ids = await r.smembers(user_vs_key)
        logger.debug(f"VS ids {vs_ids}")
        results = []
        
        for vs_id in vs_ids:
            if isinstance(vs_id, bytes):
                vs_id = vs_id.decode('utf-8')
            
            # دریافت متادیتای هر VS
            meta = await r.hgetall(f"vs_meta:{vs_id}")
            logger.debug(f"VS metadata {meta}")
            if meta:
                def get_val(key_bytes):
                # چک کردن هم کلید بایت هم رشته
                    val = meta.get(key_bytes) or meta.get(key_bytes.decode('utf-8'))
                    return val.decode('utf-8') if isinstance(val, bytes) else str(val)
                results.append({
                    "id": vs_id,
                    "name": get_val(b"name") or "Unnamed",
                    "created_at": int(get_val(b"created_at") or 0)
                })
        logger.debug(f"final result {results}")
        logger.debug("END DEBUG list_vector_stores")
        return results
    except Exception as e:
        logger.error(f"Error listing vector stores for user {user_id}: {e}")
        raise HTTPException(status_code=503, detail="Database error.")

