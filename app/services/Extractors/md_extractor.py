from langchain_text_splitters import MarkdownHeaderTextSplitter

def extract_from_md(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    # خروجی مستقیم اسپیلیتر را به فرمت دلخواه تبدیل می‌کنیم
    docs = markdown_splitter.split_text(text)
    return [{"text": d.page_content, "metadata": d.metadata} for d in docs]