# app\utils\chroma_filters.py
from typing import Dict, Any, List

def map_query_filters_to_chroma(filters: dict | None) -> dict | None:
    if not filters:
        return None

    allowed_keys = {"file_id", "file_name", "page_number", "chunk_index"}
    mapped: dict[str, Any] = {}

    for key, value in filters.items():
        # اگر کاربر اشتباهی "metadata.page_number" فرستاد، اصلاحش کن
        if key.startswith("metadata."):
            key = key.split("metadata.", 1)[1]

        if key not in allowed_keys:
            continue

        mapped[key] = value

    return mapped or None



def map_to_chroma_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps user-friendly filters to ChromaDB's query filter syntax.
    Handles nested metadata fields like 'page_number'.
    """
    chroma_query_filter = {}
    for key, value in filters.items():
        if isinstance(value, dict):
            # اگر value خودش دیکشنری بود (مثلاً {"$eq": 2})
            chroma_query_filter[key] = value
        elif isinstance(value, list):
            # اگر value لیست بود (مثلاً {"$in": [1, 2]})
            chroma_query_filter[key] = {"$in": value}
        else:
            # اگر value یک مقدار ساده بود (مثلاً 2)
            chroma_query_filter[key] = {"$eq": value}
    return chroma_query_filter

def map_metadata_field(key: str) -> str:
    """
    Maps a potential user-facing metadata key to the internal ChromaDB key format.
    For example, 'page_number' might become 'metadata.page_number'.
    """
    # این تابع برای زمانی است که بخواهیم فیلترها را روی metadata ی خاصی اعمال کنیم
    # ChromaDB خودش این کار را با '.' انجام می‌دهد، مثلا {"metadata.page_number": {"$eq": 2}}
    # پس این تابع ممکن است لازم نباشد اگر فیلترها مستقیم کلیدهای metadata را هدف قرار دهند.
    # اما اگر بخواهیم یک کلید ساده مثل "page" را به "metadata.page" تبدیل کنیم، این مفید است.
    # برای سادگی فعلی، فرض می‌کنیم کلیدها مستقیم metadata هستند.
    return key
