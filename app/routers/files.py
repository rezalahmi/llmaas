# app/routers/files.py
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status

from app.schemas.files import FileUploadResponse, FileListResponse
from app.dependencies import get_current_user
from app.postgres_client import get_pg

from app.services.file_service import save_file_stream, generate_file_id
from app.services.file_metadata_service import (
    create_file_uploading,
    mark_file_ready,
    mark_file_failed,
    list_files_by_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    
    external_user_id = user.get("external_user_id")
    api_key_id = user.get("api_key_id")

    logger.info(f"UPLOAD user payload: {user}")
    logger.info(f"UPLOAD external_user_id={external_user_id}, api_key_id={api_key_id}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")

    file_id = generate_file_id()

    try:
        await create_file_uploading(
            pg,
            file_id=file_id,
            external_user_id=external_user_id,
            api_key_id=api_key_id,
            filename=file.filename,
            content_type=file.content_type,
        )

        try:
            file_meta = await save_file_stream(file, file_id=file_id)
        except Exception as e:
            logger.error(f"Disk I/O Error during file upload: {str(e)}", exc_info=True)
            await mark_file_failed(pg, file_id=file_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save file to storage."
            )

        await mark_file_ready(
            pg,
            file_id=file_id,
            ext=file_meta["ext"],
            bytes_=file_meta["bytes"],
            storage_key=file_meta["storage_key"],
            storage_path=file_meta["path"],
            sha256=file_meta["sha256"],
            storage_backend="disk",
        )

        return FileUploadResponse(
            file_id=file_id,
            filename=file_meta["filename"],
            bytes=file_meta["bytes"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}", exc_info=True)
        try:
            await mark_file_failed(pg, file_id=file_id, error=str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.get("/", response_model=FileListResponse)
async def list_user_files(
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    print(f"START DEBUG LIST USER FILES")
    print(f"user data {user}")
    user_id = user.get("external_user_id")

    try:
        rows = await list_files_by_user(pg, external_user_id=user_id)

        files = [
            {
                "file_id": row["id"],
                "filename": row["filename"],
                "bytes": row["bytes"],
            }
            for row in rows
        ]

        return FileListResponse(files=files)

    except Exception as e:
        logger.error(f"Error listing files for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve file list from database."
        )
