import fitz  # PyMuPDF


def extract_from_pdf(file_path):
    pages_data = []
    doc = fitz.open(file_path)
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages_data.append({
                "text": text,
                "metadata": {"page_number": i + 1}
            })
    doc.close()
    return pages_data