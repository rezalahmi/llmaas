import json
import yaml # کتابخانه برای فرمت‌دهی بهتر

def extract_from_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # تبدیل به فرمت متنی خوانا برای مدل
    # اگر JSON لیستی از اشیاء باشد، هر شیء را یک چانک در نظر می‌گیریم
    if isinstance(data, list):
        documents = []
        for i, item in enumerate(data):
            text = yaml.dump(item, allow_unicode=True)
            documents.append({"text": text, "metadata": {"index": i}})
        return documents
    else:
        # اگر کل فایل یک آبجکت است
        text = yaml.dump(data, allow_unicode=True)
        return [{"text": text, "metadata": {"source": "json"}}]
    
def extract_from_jsonl(file_path):
    documents = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                item = json.loads(line)
                documents.append({"text": yaml.dump(item), "metadata": {"line": i}})
            except:
                continue
    return documents
