import httpx
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# گرفتن آدرس از محیط (با مقدار پیش‌فرض داکر)
RERANKER_URL = os.getenv("RERANKER_URL", "http://host.docker.internal:9100/rerank")

async def rerank_results(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    نتایج جستجو را به ریرنکر می‌فرستد و آن‌ها را بر اساس امتیاز جدید مرتب می‌کند.
    """
    if not results:
        return results

    # استخراج متن‌ها برای فرستادن به ریرنکر
    documents = [item["text"] for item in results]
    
    payload = {"query": query, "documents": documents}
    
    try:
        async with httpx.AsyncClient() as client:
            # timeout مناسب برای ریرنکر
            response = await client.post(RERANKER_URL, json=payload, timeout=15.0)
            response.raise_for_status()
            reranked_data = response.json()["results"]
    except Exception as e:
        logger.error(f"Reranker service failed: {e}. Returning original search results.")
        # اگر ریرنکر خطا داد، نتایج اصلی را بدون تغییر برگردان (Graceful Degradation)
        return results

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
            
    return sorted_results
