import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from api.application import create_app
from config.settings import Settings


QUESTIONS = {
    "python": {"type": "noul", "instructions": "Is Python mentioned?"},
    "experience": {
        "type": "choice", "instructions": "Does the resume document API experience?",
        "criteria": {"yes": "API experience documented", "unknown": "Not established"},
    },
    "depth": {"type": "score", "instructions": "Rate Python experience", "criteria": ["Basic", "Advanced"]},
}
ANSWERS = {
    "python": {"type": "noul", "noul": 0.9},
    "experience": {"type": "choice", "choice": "yes"},
    "depth": {"type": "score", "score": 0.8},
}


class ScreeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests = []
        self.clients = []
        self.result = {"answers": ANSWERS, "usage": {"cost": 0.001}}
        self.status = 200
        self.timeout = False
        self.invalid_json = False
        original_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if self.timeout:
                raise httpx.ReadTimeout("PRIVATE_PROVIDER_DETAILS", request=request)
            if self.invalid_json:
                return httpx.Response(200, text="PRIVATE_INVALID_JSON")
            return httpx.Response(self.status, json=self.result)

        def create_client() -> httpx.AsyncClient:
            client = original_client(transport=httpx.MockTransport(handler))
            self.clients.append(client)
            return client

        self.enterContext(patch("integrations.jev.httpx.AsyncClient", side_effect=create_client))
        self.enterContext(patch("domains.screening.factory.Settings", return_value=Settings(
            _env_file=None, openrouter_api_key="test-key", jev_model="test-jev",
        )))
        self.client = self.enterContext(TestClient(create_app()))

    def tearDown(self) -> None:
        for client in self.clients:
            self.assertTrue(client.is_closed)

    def screen(self) -> httpx.Response:
        return self.client.post('/api/screen', json={
            "resume": "Python developer with API experience.",
            "questions": json.dumps(QUESTIONS),
        })

    def test_string_questions_are_parsed_and_sent_to_jev(self) -> None:
        response = self.screen()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "data": self.result})
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(str(self.requests[0].url), 'https://openrouter.ai/api/alpha/decisions')
        self.assertEqual(json.loads(self.requests[0].content), {
            "model": "test-jev", "state": "Python developer with API experience.", "questions": QUESTIONS,
        })

    def test_invalid_input_never_reaches_jev(self) -> None:
        valid = {"resume": "Python developer", "questions": json.dumps(QUESTIONS)}
        cases = [
            {}, {**valid, "resume": " "}, {**valid, "resume": "x" * 60001},
            {**valid, "questions": QUESTIONS}, {**valid, "questions": "not json"},
            {**valid, "questions": "{}"}, {**valid, "questions": "[]"},
            {**valid, "questions": json.dumps({"questions": QUESTIONS})},
            {**valid, "questions": json.dumps({"q": {"type": "choice", "instructions": "Pick"}})},
            {**valid, "questions": json.dumps({str(i): QUESTIONS['python'] for i in range(26)})},
            {**valid, "model": "untrusted-model"},
        ]
        for body in cases:
            with self.subTest(fields=list(body)):
                self.assertEqual(self.client.post('/api/screen', json=body).status_code, 422)
        self.assertEqual(self.requests, [])

    def test_http_errors_are_sanitized_without_retries(self) -> None:
        for status in (401, 429, 500):
            self.status = status
            before = len(self.requests)
            response = self.screen()
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()['detail'], 'Screening provider failed')
            self.assertEqual(len(self.requests), before + 1)

    def test_timeout_is_504(self) -> None:
        self.timeout = True
        response = self.screen()
        self.assertEqual(response.status_code, 504)
        self.assertNotIn('PRIVATE_PROVIDER_DETAILS', response.text)

    def test_invalid_or_missing_answers_are_502(self) -> None:
        for payload in ({}, {"answers": []}, {"answers": {}}, {"answers": {"python": ANSWERS['python']}}):
            self.result = payload
            response = self.screen()
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()['detail'], 'Screening provider returned invalid answers')

    def test_invalid_json_is_502(self) -> None:
        self.invalid_json = True
        response = self.screen()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('PRIVATE_INVALID_JSON', response.text)

    def test_openapi_exposes_string_fields(self) -> None:
        schema = self.client.get('/openapi.json').json()
        fields = schema['components']['schemas']['ScreeningRequest']['properties']
        self.assertEqual(fields['resume']['type'], 'string')
        self.assertEqual(fields['questions']['type'], 'string')
        self.assertIn('200', schema['paths']['/api/screen']['post']['responses'])
