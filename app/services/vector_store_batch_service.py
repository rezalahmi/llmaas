import uuid
from typing import Optional, Dict
from datetime import datetime

async def create_batch_record(pg, vector_store_id: str, api_key_id: int, total_files: int) -> str:
    batch_id = f"vsfb_{uuid.uuid4().hex[:20]}"
    query = """
        INSERT INTO vector_store_file_batches (id, vector_store_id, api_key_id, status, total_files)
        VALUES ($1, $2, $3, 'in_progress', $4)
        RETURNING id
    """
    await pg.execute(query, batch_id, vector_store_id, api_key_id, total_files)
    return batch_id

async def get_batch_status(pg, batch_id: str, api_key_id: int) -> Optional[Dict]:
    query = """
        SELECT id, vector_store_id, status, total_files, completed_files, failed_files, created_at
        FROM vector_store_file_batches
        WHERE id = $1 AND api_key_id = $2
    """
    row = await pg.fetchrow(query, batch_id, api_key_id)
    if not row:
        return None
    
    return {
        "id": row["id"],
        "vector_store_id": row["vector_store_id"],
        "status": row["status"],
        "file_counts": {
            "total": row["total_files"],
            "completed": row["completed_files"],
            "failed": row["failed_files"],
            "in_progress": row["total_files"] - (row["completed_files"] + row["failed_files"])
        },
        "created_at": int(row["created_at"].timestamp())
    }

async def update_batch_progress(pg, batch_id: str, success: bool):
    # آپدیت شمارنده‌ها و تغییر وضعیت نهایی در صورت اتمام
    column = "completed_files" if success else "failed_files"
    query = f"""
        UPDATE vector_store_file_batches
        SET {column} = {column} + 1,
            updated_at = NOW(),
            status = CASE 
                WHEN (completed_files + failed_files + 1) >= total_files THEN 'completed'
                ELSE status
            END
        WHERE id = $1
    """
    await pg.execute(query, batch_id)
