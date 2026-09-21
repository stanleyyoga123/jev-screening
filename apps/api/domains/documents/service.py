from pdfminer.pdfexceptions import PDFException
from pdfplumber.utils.exceptions import PdfminerException

from domains.documents.model import InvalidDocumentError
from integrations.reader import PdfReader


class DocumentsService:
    def __init__(self) -> None:
        self._reader = PdfReader()

    def parse(self, content: bytes) -> str:
        try:
            return self._reader.read(content)
        except (PdfminerException, PDFException) as exc:
            raise InvalidDocumentError(
                "Unable to read PDF; upload a valid PDF without password protection"
            ) from exc
