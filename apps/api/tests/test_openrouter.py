import json
import unittest
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from config.settings import Settings
from integrations.openrouter import OpenRouterProvider
from integrations.jev import JevResponse


QUESTIONS = {"skill": {"type": "noul", "instructions": "Is Python mentioned?"}}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def settings(self):
        return Settings(_env_file=None, openrouter_api_key="test-key")

    @asynccontextmanager
    async def provider(
        self, handler: Callable[[httpx.Request], httpx.Response]
    ) -> AsyncIterator[OpenRouterProvider]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch("integrations.openrouter.httpx.AsyncClient", return_value=client):
            provider = OpenRouterProvider(self.settings())
        try:
            async with provider:
                yield provider
                self.assertFalse(client.is_closed)
        finally:
            self.assertTrue(client.is_closed)

    async def test_request_and_response(self):
        result = {
            "answers": {"skill": {"type": "noul", "noul": 0.9}},
            "usage": {"cost": 0.001},
        }

        def handler(request):
            self.assertEqual(str(request.url), "https://openrouter.ai/api/alpha/decisions")
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(json.loads(request.content), {
                "model": "~typesafe/jev-latest", "state": "Python", "questions": QUESTIONS
            })
            self.assertEqual(request.extensions["timeout"]["read"], 25)
            return httpx.Response(200, json=result)

        async with self.provider(handler) as provider:
            response = await provider.hit("Python", QUESTIONS)
            self.assertIsInstance(response, JevResponse)
            self.assertEqual(response.answers, result["answers"])
            self.assertEqual(response.model_dump(), result)
            await provider.hit("Python", QUESTIONS)

    async def test_invalid_inputs_never_send(self):
        def handler(request):
            self.fail("Invalid input reached the network")

        async with self.provider(handler) as provider:
            cases = [
                (" ", QUESTIONS),
                ("Python", {}),
                ("Python", {"q": {"type": "choice", "instructions": "Pick"}}),
                ("Python", {"q": {"type": "score", "instructions": "Rate", "criteria": {"bad": "shape"}}}),
                ("Python", {"q": {"type": "noul", "instructions": "Check", "criteria": []}}),
            ]
            for state, questions in cases:
                with self.subTest(state=state, questions=questions):
                    with self.assertRaises(ValidationError):
                        await provider.hit(state, questions)

    async def test_http_errors(self):
        for status in (401, 429, 500):
            with self.subTest(status=status):
                async with self.provider(
                    lambda request: httpx.Response(status, json={"error": "failure"})
                ) as provider:
                    with self.assertRaises(httpx.HTTPStatusError):
                        await provider.hit("Python", QUESTIONS)

    async def test_invalid_responses(self):
        for response in (httpx.Response(200, text="not json"),
                         httpx.Response(200, json=[]),
                         httpx.Response(200, json={}),
                         httpx.Response(200, json={"answers": []}),
                         httpx.Response(200, json={"answers": None})):
            async with self.provider(
                lambda request: response
            ) as provider:
                with self.assertRaises(ValidationError):
                    await provider.hit("Python", QUESTIONS)

    async def test_missing_requested_answers(self):
        async with self.provider(
            lambda request: httpx.Response(200, json={"answers": {"other": 0.9}})
        ) as provider:
            with self.assertRaisesRegex(ValueError, "missing requested answers"):
                await provider.hit("Python", QUESTIONS)

    async def test_timeout_propagates(self):
        def handler(request):
            raise httpx.ReadTimeout("Timed out", request=request)

        async with self.provider(handler) as provider:
            with self.assertRaises(httpx.ReadTimeout):
                await provider.hit("Python", QUESTIONS)

    def test_blank_key_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, openrouter_api_key=" ")

    def test_secret_hidden(self):
        self.assertNotIn("test-key", repr(self.settings()))
