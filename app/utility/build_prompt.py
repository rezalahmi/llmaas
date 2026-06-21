from app.schemas.file_search import FileSearchResponse, FileSearchResultChunk
from app.token_counter import count_tokens  # ایمپورت این تابع ضروری است

# =============================================================================
# تنظیمات پیش‌فرض برای مدل‌ها (تعداد توکن‌های Context Window)
# =============================================================================
MODEL_CONTEXT_WINDOWS = {
    "gemma3:12b": 8192,
    "gemma3:4b": 8192,
    "llama3:8b": 8192,
    "mistral:7b": 8192,
    "phi3:3.8b": 8192,
    # ... مدل‌های دیگر خود را اینجا اضافه کنید
}
DEFAULT_CONTEXT_WINDOW = 8000
CONTEXT_SAFETY_MARGIN = 200  # حاشیه امن برای جلوگیری از خطای دقیقاً روی مرز


def _build_context_string(fs_response: FileSearchResponse) -> str:
    """ساخت رشته context از نتایج جستجو"""
    if not fs_response or not fs_response.results:
        return ""
    
    context_parts = []
    for i, chunk in enumerate(fs_response.results, start=1):
        meta = chunk.metadata or {}
        filename = meta.get("filename") or meta.get("file_name") or meta.get("source") or "unknown"
        page_number = meta.get("page_number", "unknown")
        section = meta.get("section", None)
        sheet = meta.get("sheet")
        row = meta.get("row")
        slide_number = meta.get("slide_number")
        
        header_lines = [f"Chunk #{i}", f"filename: {filename}", f"score: {chunk.score}"]
        if page_number: header_lines.append(f"page_number: {page_number}")
        if sheet: header_lines.append(f"sheet: {sheet}")
        if row: header_lines.append(f"row: {row}")
        if slide_number: header_lines.append(f"slide_number: {slide_number}")
        if section: header_lines.append(f"section: {section}")

        header = "\n".join(header_lines)
        context_parts.append(f"[منبع {i}]\n{header}\ntext:\n{chunk.text}")
    
    return "\n\n---\n\n".join(context_parts)


def _truncate_history_by_tokens(history: list[dict], max_tokens: int) -> list[dict]:
    """
    برش زدن تاریخچه از سمت قدیمی‌ترین پیام‌ها تا جایی که در بودجه توکن جا بشود.
    پیام‌های جدیدتر اولویت بیشتری دارند.
    """
    if not history or max_tokens <= 0:
        return []
    
    # history شامل پیام فعلی هم هست، پس فقط history[:-1] را برای گذشته در نظر می‌گیریم
    past_messages = history[:-1] if len(history) > 1 else []
    
    if not past_messages:
        return []

    selected_messages = []
    current_tokens = 0
    
    # پیمایش از آخر (جدیدترین) به اول (قدیمی‌ترین)
    for msg in reversed(past_messages):
        # محاسبه توکن این پیام با فرمت ساده
        msg_text = f"{msg.get('role', '')}: {msg.get('content', '')}"
        msg_tokens = count_tokens(msg_text)
        
        if current_tokens + msg_tokens > max_tokens:
            break  # بودجه پر شد، بقیه پیام‌های قدیمی‌تر حذف می‌شوند
            
        selected_messages.insert(0, msg) # اضافه کردن به ابتدای لیست برای حفظ ترتیب زمانی
        current_tokens += msg_tokens
        
    return selected_messages


def build_rag_prompt_with_history(
    conversation_history: list[dict],
    fs_response: FileSearchResponse,
    current_query: str,
    model_name: str = "default",
    max_output_tokens: int = 2048
) -> str:
    """
    ساخت RAG prompt با مدیریت هوشمند بودجه توکن برای مدل‌های کوچک.
    """
    
    # ۱. محاسبه اندازه Context Window مدل
    context_window = MODEL_CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)

    # ۲. محاسبه توکن‌های ثابت و اجباری
    system_instructions = """شما یک دستیار دقیق، محتاط و مبتنی بر سند هستید.
وظیفه شما:
- فقط و فقط از «چانک‌های بازیابی‌شده» برای پاسخ استفاده کن.
- اگر پاسخ در چانک‌ها نیست، صریح بگو «اطلاعات کافی در اسناد موجود یافت نشد».
- هیچ فرضی نزن و از دانش بیرونی استفاده نکن.
- پاسخ را به زبان پرسش کاربر و روشن بده.
- در متن حتماً از شماره منبع به شکل [1]، [2] و ... استفاده کن.
- اگر سوال ارجاعی به پیام‌های قبلی دارد، از تاریخچه برای درک منظور استفاده کن."""
    
    system_tokens = count_tokens(system_instructions)
    query_tokens = count_tokens(current_query)
    
    retrieved_context = _build_context_string(fs_response)
    context_tokens = count_tokens(retrieved_context) if retrieved_context else 0
    
    # ۳. محاسبه بودجه باقیمانده برای تاریخچه
    available_for_history = (
        context_window 
        - max_output_tokens 
        - system_tokens 
        - context_tokens 
        - query_tokens 
        - CONTEXT_SAFETY_MARGIN
    )
    
    # لاگ برای دیباگ در آینده
    if available_for_history < 0:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"[RAG BUDGET] Context too large! Window: {context_window}, "
            f"Reserved(System+Ctx+Query+Out): {system_tokens + context_tokens + query_tokens + max_output_tokens}. "
            f"History will be empty."
        )
        available_for_history = 0

    # ۴. برش زدن تاریخچه بر اساس بودجه
    truncated_history = _truncate_history_by_tokens(conversation_history, available_for_history)
    
    # ۵. ساخت نهایی Prompt
    if not retrieved_context:
        history_text = _format_history_text(truncated_history)
        prompt = f"""{system_instructions}

⚠️ هیچ سند مرتبطی با سوال فعلی پیدا نشد.

{history_text}
پرسش فعلی کاربر:
{current_query}

بر اساس اسنادی که در اختیار دارم، پاسخی پیدا نکردم."""
        return prompt.strip()

    history_text = _format_history_text(truncated_history)
    
    prompt = f"""{system_instructions}

═══════════════════════════════════════
چانک‌های بازیابی‌شده (فقط بر اساس این‌ها پاسخ بده):
═══════════════════════════════════════
{retrieved_context}
═══════════════════════════════════════
{history_text}
───────────────────────────────────────
پرسش فعلی کاربر:
{current_query}
───────────────────────────────────────

حالا یک پاسخ منسجم، کوتاه و دقیق بده."""

    return prompt.strip()


def _format_history_text(conversation_history: list[dict]) -> str:
    """فرمت‌بندی تاریخچه (فقط پیام‌های پاس داده شده را فرمت می‌کند)"""
    if not conversation_history:
        return ""
    
    lines = []
    for msg in conversation_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        if not content.strip():
            continue
            
        if role == "user":
            lines.append(f"👤 کاربر: {content}")
        elif role == "assistant":
            lines.append(f"🤖 دستیار: {content}")
    
    if not lines:
        return ""
        
    history_section = """═══════════════════════════════════════
تاریخچه مکالمه (برای درک سیاق سوال فعلی):
═══════════════════════════════════════
""" + "\n".join(lines) + """
═══════════════════════════════════════
"""
    return history_section


# تابع قدیمی برای جلوگیری از خطای ایمپورت در جاهای دیگر (اگر دارد)
def build_rag_prompt_from_file_search(user_query: str, fs_response: FileSearchResponse) -> str:
    return build_rag_prompt_with_history(
        conversation_history=[{"role": "user", "content": user_query}],
        fs_response=fs_response,
        current_query=user_query
    )