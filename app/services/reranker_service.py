import httpx
import os
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# گرفتن آدرس از محیط (با مقدار پیش‌فرض داکر)
RERANKER_URL = os.getenv("RERANKER_URL", "http://host.docker.internal:9100/rerank")


class RerankerOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED_FALLBACK = "failed_fallback"
    ELIMINATED_ALL = "eliminated_all"


@dataclass(frozen=True)
class RerankerResult:
    results: List[Dict[str, Any]]
    outcome: RerankerOutcome
    failure: str | None = None


async def rerank_results_with_status(
    query: str, results: List[Dict[str, Any]]
) -> RerankerResult:
    """
    نتایج جستجو را به ریرنکر می‌فرستد و آن‌ها را بر اساس امتیاز جدید مرتب می‌کند.
    """
    if not results:
        return RerankerResult(results, RerankerOutcome.ELIMINATED_ALL)

    # استخراج متن‌ها برای فرستادن به ریرنکر
    documents = [item["text"] for item in results]
    
    payload = {"query": query, "documents": documents}
    
    try:
        async with httpx.AsyncClient() as client:
            # timeout مناسب برای ریرنکر
            response = await client.post(RERANKER_URL, json=payload, timeout=15.0)
            response.raise_for_status()
            reranked_data = response.json()["results"]
    except httpx.TimeoutException:
        logger.error("Reranker service timed out. Returning original search results.")
        return RerankerResult(results, RerankerOutcome.FAILED_FALLBACK, "timeout")
    except Exception:
        logger.error(
            "Reranker service failed. Returning original search results.",
            exc_info=True,
        )
        # اگر ریرنکر خطا داد، نتایج اصلی را بدون تغییر برگردان (Graceful Degradation)
        return RerankerResult(
            results, RerankerOutcome.FAILED_FALLBACK, "provider_error"
        )

    # حالا باید نتایج مرتب شده توسط ریرنکر را با داده‌های اصلی (متادیتاها و غیره) ترکیب کنیم
    # چون ممکن است متن تکراری داشته باشیم، از دیکشنری برای نگاشت استفاده می‌کنیم
    text_to_items = {}
    for item in results:
        text = item["text"]
        if text not in text_to_items:
            text_to_items[text] = []
        text_to_items[text].append(item)
    
    sorted_results = []
    for rerank_index, rank_item in enumerate(reranked_data, start=1):
        text = rank_item["text"]
        score = rank_item["score"]
        
        if text in text_to_items and text_to_items[text]:
            # برداشتن اولین آیتم موجود برای این متن
            original_item = text_to_items[text].pop(0)
            # به‌روزرسانی امتیاز با امتیاز دقیق‌ترِ ریرنکر
            original_item["rerank_score"] = score
            original_item["rerank_rank"] = rerank_index
            original_item["score"] = score
            sorted_results.append(original_item)
            
    if not sorted_results:
        return RerankerResult([], RerankerOutcome.ELIMINATED_ALL)
    return RerankerResult(sorted_results, RerankerOutcome.COMPLETED)


async def rerank_results(
    query: str, results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Backward-compatible public API used by existing file-search callers."""
    return (await rerank_results_with_status(query, results)).results
