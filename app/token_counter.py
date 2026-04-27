# app\token_counter.py
import os
import tiktoken

# اجبار به استفاده از فایل local
os.environ["TIKTOKEN_CACHE_DIR"] = "/app"

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))
