from bs4 import BeautifulSoup

def extract_from_html(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    # حذف تگ‌های غیرمفید
    for script in soup(["script", "style", "nav", "footer", "head"]):
        script.extract()
    
    text = soup.get_text(separator="\n", strip=True)
    return [{"text": text, "metadata": {"source": "html"}}]
