import io


def extract_text_from_pdf(file_obj) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(file_obj.read()))
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return '\n'.join(text).strip()


def extract_text_from_docx(file_obj) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_obj.read()))
    text = []
    for para in doc.paragraphs:
        if para.text.strip():
            text.append(para.text.strip())
    return '\n'.join(text).strip()


def extract_cv_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    if name.endswith('.pdf'):
        return extract_text_from_pdf(uploaded_file)
    elif name.endswith('.docx'):
        return extract_text_from_docx(uploaded_file)
    elif name.endswith('.txt'):
        return uploaded_file.read().decode('utf-8', errors='ignore').strip()
    return ''
