def extract_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    # برای TXT کل متن را به عنوان یک واحد برمی‌گردانیم (بدون شماره صفحه)
    return [{"text": text, "metadata": {}}]