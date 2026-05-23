from docx import Document

def extract_from_docx(file_path):
    doc = Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    return [{"text": text, "metadata": {"source": "docx"}}]
