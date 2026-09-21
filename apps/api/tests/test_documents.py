import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.application import create_app
from domains.documents.factory import get_documents_service
from domains.documents.schema import DocumentResponse
from domains.documents.service import DocumentsService


def make_pdf(*pages: str) -> bytes:
    """Build a small real PDF using synthetic, plain ASCII page text."""
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids ['
        + b' '.join(f'{4 + i * 2} 0 R'.encode() for i in range(len(pages)))
        + f'] /Count {len(pages)} >>'.encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    for i, text in enumerate(pages):
        objects.append(
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Resources << /Font << /F1 3 0 R >> >> '
            + f'/Contents {5 + i * 2} 0 R >>'.encode()
        )
        stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
        objects.append(
            f'<< /Length {len(stream)} >>\nstream\n'.encode()
            + stream + b'\nendstream'
        )
    content = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(content)
    content.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        content.extend(f'{offset:010d} 00000 n \n'.encode())
    content.extend(
        f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n'
        f'startxref\n{xref}\n%%EOF\n'.encode()
    )
    return bytes(content)


class DocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.client = self.enterContext(TestClient(self.app))

    def test_pdf_upload_returns_extracted_string(self) -> None:
        response = self.client.post('/api/documents/parse', files={
            'file': ('resume.pdf', make_pdf('Python developer', 'API experience'), 'application/pdf'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True, 'data': 'Python developer\n\nAPI experience',
        })

    def test_blank_pdf_returns_empty_string(self) -> None:
        response = self.client.post('/api/documents/parse', files={
            'file': ('blank.pdf', make_pdf(''), 'application/pdf'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'data': ''})

    def test_invalid_pdf_returns_422(self) -> None:
        for content in (b'', b'not a PDF', b'%PDF-1.4\ninvalid'):
            with self.subTest(content=content):
                response = self.client.post('/api/documents/parse', files={
                    'file': ('broken.pdf', content, 'application/pdf'),
                })
                self.assertEqual(response.status_code, 422)
                self.assertIn('Unable to read PDF', response.json()['detail'])

    def test_non_pdf_rejected_before_extraction(self) -> None:
        service = DocumentsService()
        self.app.dependency_overrides[get_documents_service] = lambda: service
        with patch.object(service, 'parse') as parse:
            response = self.client.post('/api/documents/parse', files={
                'file': ('resume.txt', b'Python developer', 'text/plain'),
            })
            self.assertEqual(response.status_code, 415)
            parse.assert_not_called()

    def test_file_is_required(self) -> None:
        self.assertEqual(self.client.post('/api/documents/parse').status_code, 422)

    def test_openapi_declares_upload_and_string_response(self) -> None:
        schema = self.client.get('/openapi.json').json()
        operation = schema['paths']['/api/documents/parse']['post']
        self.assertIn('multipart/form-data', operation['requestBody']['content'])
        self.assertIn('200', operation['responses'])
        self.assertEqual(DocumentResponse.model_json_schema()['properties']['data']['type'], 'string')
