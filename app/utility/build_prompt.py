from app.schemas.file_search import FileSearchResponse, FileSearchResultChunk

def build_rag_prompt_from_file_search(user_query: str, fs_response: FileSearchResponse) -> str:
    """
    Build a RAG prompt from file search results.

    Args:
        user_query: The user's question.
        fs_response: Search results from vector store.

    Returns:
        A prompt string to send to the LLM.
    """

    if not fs_response or not fs_response.results:
        return f"""
شما باید فقط بر اساس اسناد پاسخ بدهید.
در حال حاضر هیچ سند مرتبطی پیدا نشد.

پرسش کاربر:
{user_query}

اگر پاسخ در اسناد نیست، صریح بگو:
«بر اساس اسنادی که در اختیار دارم، پاسخی پیدا نکردم.»
""".strip()

    context_parts = []
    for i, chunk in enumerate(fs_response.results, start=1):
        meta = chunk.metadata or {}
        filename = meta.get("filename") or meta.get("file_name") or meta.get("source") or "unknown"
        page_number = meta.get("page_number", "unknown")
        section = meta.get("section", None)
        # شناسایی متادیتای خاص برای Excel یا PPTX
        sheet = meta.get("sheet")
        row = meta.get("row")
        slide_number = meta.get("slide_number")
        header_lines = [
            f"Chunk #{i}",
            f"filename: {filename}",
            f"score: {chunk.score}",
        ]
        # اضافه کردن داینامیک متادیتا
        if page_number: header_lines.append(f"page_number: {page_number}")
        if sheet: header_lines.append(f"sheet: {sheet}")
        if row: header_lines.append(f"row: {row}")
        if slide_number: header_lines.append(f"slide_number: {slide_number}")
        if section: header_lines.append(f"section: {section}")

        header = "\n".join(header_lines)
        context_parts.append(f"[منبع {i}]\n{header}\ntext:\n{chunk.text}")

    retrieved_context = "\n\n---\n\n".join(context_parts)

    prompt = f"""
شما یک دستیار دقیق، محتاط و مبتنی بر سند هستید.

وظیفه شما:
- فقط و فقط از «چانک‌های بازیابی‌شده» برای پاسخ استفاده کن.
- اگر پاسخ در چانک‌ها نیست، صریح بگو «اطلاعات کافی در اسناد موجود یافت نشد».
- هیچ فرضی نزن و از دانش بیرونی استفاده نکن.
- پاسخ را به زبان پرسش کاربر و روشن بده.
- اگر مناسب بود، در انتهای پاسخ به chunkهای مرتبط اشاره کن.

فرمت پاسخ:
- پاسخ اصلی
- در صورت نیاز: منبع

چانک‌های بازیابی‌شده:
{retrieved_context}

پرسش کاربر:
{user_query}

حالا یک پاسخ منسجم، کوتاه و دقیق بده.
- در متن حتماً از شماره منبع به شکل [1]، [2] و ... استفاده کن.

""".strip()

    return prompt
