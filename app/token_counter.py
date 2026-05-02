import os
import tiktoken

CACHE_DIR = r"C:\Users\Administrator\Projects\develop\llmaas\tiktoken_cache"
MODEL_PATH = os.path.join(CACHE_DIR, "cl100k_base.tiktoken")

_enc = None


def _load_encoder_safely():
    global _enc
    if _enc is not None:
        return _enc

    try:
        if os.path.exists(MODEL_PATH):
            _enc = tiktoken.Encoding.from_file(MODEL_PATH)
            return _enc
        else:
            raise FileNotFoundError("Model file not found")
    except Exception as e:
        # اگر هر خطایی در لودینگ پیش بیاید فقط هشدار چاپ کن و None برگردان
        print(f"[token_counter] Warning: failed to load tiktoken encoder ({e}), fallback to approximate mode.")
        return None


def count_tokens(text: str) -> int:
    """
    اگر tiktoken فعال بود، دقیق می‌شمارد.
    در غیر این صورت با تقریب 1.3 توکن به‌ازای هر کلمه محاسبه می‌کند.
    """
    enc = _load_encoder_safely()
    if enc:
        try:
            return len(enc.encode(text))
        except Exception as e:
            print(f"[token_counter] Warning: encoding failed with error {e}, using fallback.")
    
    # Fallback: تخمین ساده
    word_count = len(text.split())
    approx_tokens = int(word_count * 1.3)
    return approx_tokens
