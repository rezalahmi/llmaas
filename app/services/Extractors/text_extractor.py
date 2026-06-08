# app\services\Extractors\text_extractor.py
def extract_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    # برای TXT کل متن را به عنوان یک واحد برمی‌گردانیم (بدون شماره صفحه)
    return [{"text": text, "metadata": {}}]

def extract_generic_text(file_path):
    # این تابع برای فایل‌هایی که ساختار متنی ساده دارند استفاده می‌شود
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return [{"text": f.read(), "metadata": {"source": "raw_text"}}]
