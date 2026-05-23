from app.services.Extractors.pdf_extractor import extract_from_pdf
from app.services.Extractors.text_extractor import extract_from_txt, extract_generic_text
from app.services.Extractors.docx_extractor import extract_from_docx
from app.services.Extractors.excel_extractor import extract_from_excel
from app.services.Extractors.md_extractor import extract_from_md
from app.services.Extractors.pptx_extractor import extract_from_pptx
from app.services.Extractors.html_extractor import extract_from_html
from app.services.Extractors.json_extractor import extract_from_json, extract_from_jsonl


EXTRACTORS = {
    ".txt": extract_from_txt,
    ".md": extract_from_md,
    ".pdf": extract_from_pdf,
    ".docx": extract_from_docx,
    ".xlsx": extract_from_excel,
    ".xls": extract_from_excel,
    ".pptx": extract_from_pptx,
    ".csv": extract_generic_text, 
    ".html": extract_from_html,
    ".json": extract_from_json,
    ".jsonl": extract_from_jsonl
}

def get_raw_documents(full_path, ext):
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(f"Extension {ext} is not supported.")
    return extractor(full_path)
