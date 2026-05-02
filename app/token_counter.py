import os
import tiktoken

# Build absolute cache directory path
CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tiktoken_cache")
)

# Ensure the environment is set BEFORE loading encodings
os.environ["TIKTOKEN_CACHE_DIR"] = CACHE_DIR

# Required filename inside cache dir
MODEL_FILENAME = "cl100k_base.tiktoken"
MODEL_PATH = os.path.join(CACHE_DIR, MODEL_FILENAME)

# Global encoder object (lazy-loaded)
_enc = None


def _load_encoder_safely():
    global _enc

    # If already loaded, return it
    if _enc is not None:
        return _enc

    # Check folder existence
    if not os.path.exists(CACHE_DIR):
        raise RuntimeError(
            f"Tiktoken cache directory does NOT exist: {CACHE_DIR}\n"
            "Create it and put cl100k_base.tiktoken inside it."
        )

    # Check file existence
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Required tiktoken model file not found:\n  {MODEL_PATH}\n\n"
            "Download cl100k_base.tiktoken and place it here.\n"
            "Otherwise tiktoken will try to download from the internet and fail."
        )

    try:
        # Now safely load
        _enc = tiktoken.get_encoding("cl100k_base")
        return _enc
    except Exception as e:
        raise RuntimeError(
            "Failed to initialize tiktoken encoder.\n"
            f"Cache directory: {CACHE_DIR}\n"
            f"File exists: {os.path.exists(MODEL_PATH)}\n"
            f"Error: {str(e)}"
        )


def count_tokens(text: str) -> int:
    enc = _load_encoder_safely()
    return len(enc.encode(text))
