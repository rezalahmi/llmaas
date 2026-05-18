# app\services\Extractors\utils.py
import re

def normalize_extracted_text(text: str) -> str:
    text = text.replace("\u200c", " ")   # نیم‌فاصله‌های مشکل‌ساز در صورت نیاز
    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text)    # چند newline -> یکی
    text = re.sub(r"[ \t]+", " ", text)  # فاصله‌های تکراری -> یکی
    text = re.sub(r" ?\n ?", "\n", text) # فاصله اطراف newline
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    return text.strip()
