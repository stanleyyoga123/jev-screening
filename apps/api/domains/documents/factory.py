from domains.documents.service import DocumentsService


def get_documents_service() -> DocumentsService:
    return DocumentsService()
