# docker\stream.Dockerfile
FROM  python:3.12-slim

WORKDIR /app

# تنظیم PyPI mirror لیارا
ENV PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ENV PIP_TRUSTED_HOST=package-mirror.liara.ir

# جلوگیری از cache اضافی
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

# ✅ کپی encoding برای tiktoken (offline)
COPY tiktoken_cache/cl100k_base.tiktoken /app/cl100k_base.tiktoken

COPY app ./app

ENV TIKTOKEN_CACHE_DIR=/app

CMD ["python", "-m", "app.stream_worker"]