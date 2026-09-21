from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from domains.documents.factory import get_documents_service
from domains.documents.model import InvalidDocumentError
from domains.documents.schema import DocumentResponse
from domains.documents.service import DocumentsService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/parse", response_model=DocumentResponse)
async def parse(
    file: Annotated[UploadFile, File(description="PDF file to extract text from")],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
) -> DocumentResponse:
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=415, detail="Upload a PDF file")
        content = await file.read()
    finally:
        await file.close()

    try:
        text = await run_in_threadpool(service.parse, content)
    except InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentResponse(success=True, data=text)
