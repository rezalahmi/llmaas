# app\routers\files.py
from fastapi import APIRouter, UploadFile, File, Depends
from app.schemas.files import FileUploadResponse, FileListResponse
from app.dependencies import get_current_user
from app.services.file_service import save_file, save_file_stream
from app.redis_client import get_redis
import json

router = APIRouter(prefix="/files", tags=["Files"])




@router.post("/", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    r = Depends(get_redis)
):
    # content = await file.read()

    file_meta = await save_file_stream(file)

    user_files_key = f"user_files:{user['user_id']}"
    await r.sadd(user_files_key, file_meta["id"])

    await r.hset(
        f"file:{file_meta['id']}",
        mapping={
            "user_id": user["user_id"],
            "filename": file_meta["filename"],
            "bytes": file_meta["bytes"],
            "path": file_meta["path"]
        }
    )

    await r.incrby(f"user_storage:{user['user_id']}", file_meta["bytes"])

    return FileUploadResponse(
        file_id=file_meta["id"],
        filename=file_meta["filename"],
        bytes=file_meta["bytes"]
    )



@router.get("/", response_model=FileListResponse)
async def list_user_files(user=Depends(get_current_user), r = Depends(get_redis)):
    user_files_key = f"user_files:{user['user_id']}"
    file_ids = await r.smembers(user_files_key)

    files = []
    for fid in file_ids:
        meta = await r.get(f"file:{fid}")
        if meta:
            meta_json = json.loads(meta)
            files.append({
                "file_id": fid,
                "filename": meta_json["filename"],
                "bytes": meta_json["bytes"]
            })

    return FileListResponse(files=files)
