# app\main.py
from fastapi import FastAPI
from app.redis_client import get_redis_connection, close_redis
from app.routers.chat_router import router as chat_router
from app.routers.admin_router import router as admin_router
from app.routers.files import router as file_router
from app.routers.vector_stores import router as vs_router
from app.routers.vector_store_files import router as vsf_router
from app.routers.file_search import router as file_search_router
from app.routers.evaluations import router as evaluation_router
from app.postgres_client import connect_postgres, close_postgres

app = FastAPI()


@app.on_event("startup")
async def startup():
    await get_redis_connection()
    await connect_postgres()
    


@app.on_event("shutdown")
async def shutdown():
    await close_redis()
    await close_postgres()


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(file_router)
app.include_router(vs_router)
app.include_router(vsf_router)
app.include_router(file_search_router)
app.include_router(evaluation_router)
