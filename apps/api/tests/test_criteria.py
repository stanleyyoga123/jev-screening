import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from api.application import create_app
from config.settings import Settings
from domains.criteria.prompt import SYSTEM_PROMPT
from integrations.jev import JevRequest


QUESTIONS = {
    "role_python": {
        "type": "choice",
        "instructions": "Does the resume document Python development experience?",
        "criteria": {
            "meets": "Python development experience is explicitly documented.",
            "partial": "Some related experience is documented.",
            "does_not_meet": "Explicit evidence establishes the requirement is not met.",
            "insufficient_evidence": "The resume does not establish Python experience.",
        },
    },
}


class CriteriaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generated = json.dumps({"questions": QUESTIONS})
        self.status = 200
        self.timeout = False
        self.requests = []
        self.clients = []
        original_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if self.timeout:
                raise httpx.ReadTimeout("private provider details", request=request)
            return httpx.Response(self.status, json={
                "choices": [{
                    "message": {"role": "assistant", "content": self.generated},
                    "finish_reason": "stop",
                }],
            })

        def create_client() -> httpx.AsyncClient:
            client = original_client(transport=httpx.MockTransport(handler))
            self.clients.append(client)
            return client

        self.enterContext(patch("integrations.generator.httpx.AsyncClient", side_effect=create_client))
        self.enterContext(patch("domains.criteria.factory.Settings", return_value=Settings(
            _env_file=None, openrouter_api_key="test-key", generator_model="z-ai/glm-5.3",
        )))
        self.client = self.enterContext(TestClient(create_app()))

    def tearDown(self) -> None:
        for client in self.clients:
            self.assertTrue(client.is_closed)

    def generate(self, description: str = "Required: Python development experience.") -> httpx.Response:
        return self.client.post('/api/criteria/generate', json={"job_description": description})

    def test_generate_questions_usable_by_jev(self) -> None:
        description = "Required: Python development experience."
        response = self.generate(description)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "data": {"questions": QUESTIONS}})
        JevRequest(model="test", state="Python developer", questions=response.json()["data"]["questions"])
        self.assertEqual(len(self.requests), 1)
        payload = json.loads(self.requests[0].content)
        self.assertEqual(payload["model"], "z-ai/glm-5.3")
        self.assertEqual(payload["messages"], [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ])
        self.assertEqual(str(self.requests[0].url), "https://openrouter.ai/api/v1/chat/completions")

    def test_invalid_job_descriptions_do_not_call_provider(self) -> None:
        for body in ({}, {"job_description": " "}, {"job_description": "x" * 30001},
                     {"job_description": 123}, {"job_description": "Python", "model": "other"}):
            with self.subTest(body_type=list(body)):
                self.assertEqual(self.client.post('/api/criteria/generate', json=body).status_code, 422)
        self.assertEqual(self.requests, [])

    def test_bad_generation_returns_sanitized_502(self) -> None:
        for content in ("private broken model output", '{}', '{"questions": {}}',
                        '```json\n' + json.dumps({"questions": QUESTIONS}) + '\n```'):
            with self.subTest(content=content):
                self.generated = content
                response = self.generate()
                self.assertEqual(response.status_code, 502)
                self.assertNotIn(content, response.text)

    def test_question_contract_is_enforced(self) -> None:
        for mutate in (
            lambda question: question.update(type="score"),
            lambda question: question["criteria"].pop("insufficient_evidence"),
            lambda question: question.update(instructions=" "),
            lambda question: question.update(unexpected="field"),
        ):
            questions = json.loads(json.dumps(QUESTIONS))
            mutate(questions["role_python"])
            self.generated = json.dumps({"questions": questions})
            self.assertEqual(self.generate().status_code, 502)

    def test_http_errors_are_sanitized_without_retries(self) -> None:
        for status in (401, 429, 500):
            with self.subTest(status=status):
                self.status = status
                before = len(self.requests)
                response = self.generate()
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()["detail"], "Criteria generation provider failed")
                self.assertEqual(len(self.requests), before + 1)

    def test_timeout_returns_504(self) -> None:
        self.timeout = True
        response = self.generate()
        self.assertEqual(response.status_code, 504)
        self.assertNotIn("private provider details", response.text)

    def test_prompt_endpoint_does_not_create_provider(self) -> None:
        response = self.client.get('/api/criteria/prompt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "data": SYSTEM_PROMPT})
        self.assertEqual(self.clients, [])

    def test_openapi_exposes_request_and_response(self) -> None:
        operation = self.client.get('/openapi.json').json()['paths']['/api/criteria/generate']['post']
        self.assertIn('application/json', operation['requestBody']['content'])
        self.assertIn('200', operation['responses'])
