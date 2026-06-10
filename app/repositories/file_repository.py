# app/repositories/file_repository.py

async def get_file_by_id(pg, file_id: str, external_user_id: str):
    query = """
        SELECT id, filename, bytes, created_at
        FROM files
        WHERE id = $1 AND external_user_id = $2
        LIMIT 1
    """
    return await pg.fetchrow(query, file_id, external_user_id)
