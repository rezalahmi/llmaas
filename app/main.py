# app\main.py
from fastapi import FastAPI
from app.redis_client import init_redis, close_redis
from app.routers.chat_router import router as chat_router
from app.routers.admin_router import router as admin_router
from app.routers.files import router as file_router

app = FastAPI()


@app.on_event("startup")
async def startup():
    await init_redis()


@app.on_event("shutdown")
async def shutdown():
    await close_redis()


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(file_router)
