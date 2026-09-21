import pdfplumber
from io import BytesIO


class PdfReader:
    def read(self, content: bytes) -> str:
        pages: list[str] = []
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
