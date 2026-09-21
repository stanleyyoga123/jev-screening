import json
import unittest
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from config.settings import Settings
from integrations.generator import GeneratorMessage, GeneratorProvider, GeneratorRequest


MESSAGES = [
    GeneratorMessage(role="system", content="Generate job criteria from the supplied text."),
    GeneratorMessage(role="user", content="We need a Python developer."),
]
RESPONSE = {
    "id": "generation-test",
    "model": "z-ai/glm-5.3",
    "choices": [{
        "message": {"role": "assistant", "content": "Python development experience"},
        "finish_reason": "stop",
    }],
    "usage": {"prompt_tokens": 20, "completion_tokens": 5},
}


class GeneratorTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def provider(
        self,
        handler: Callable[[httpx.Request], httpx.Response],
        *,
        model: str = "z-ai/glm-5.3",
    ) -> AsyncIterator[GeneratorProvider]:
        settings = Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            generator_model=model,
            provider_timeout_seconds=45,
        )
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch("integrations.generator.httpx.AsyncClient", return_value=client):
            provider = GeneratorProvider(settings)
        try:
            yield provider
        finally:
            await provider.aclose()
            self.assertTrue(client.is_closed)

    async def test_request_and_response(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(request.headers["Content-Type"], "application/json")
            self.assertEqual(request.extensions["timeout"]["read"], 45)
            self.assertEqual(json.loads(request.content), {
                "model": "z-ai/glm-5.3",
                "messages": [message.model_dump() for message in MESSAGES],
                "stream": False,
            })
            return httpx.Response(200, json=RESPONSE)

        async with self.provider(handler) as provider:
            response = await provider.hit(MESSAGES)
            self.assertEqual(response.content, "Python development experience")
            self.assertEqual(response.model_dump()["usage"], RESPONSE["usage"])
            await provider.hit(MESSAGES)
        self.assertEqual(len(requests), 2)

    async def test_configured_model(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(json.loads(request.content)["model"], "example/custom-model")
            return httpx.Response(200, json=RESPONSE)

        async with self.provider(handler, model="example/custom-model") as provider:
            await provider.hit(MESSAGES)

    async def test_empty_messages_never_send(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.fail("Invalid messages reached the network")

        async with self.provider(handler) as provider:
            with self.assertRaises(ValidationError):
                await provider.hit([])

    def test_message_validation(self) -> None:
        for message in (
            {"role": "user", "content": " "},
            {"role": "tool", "content": "unsupported"},
            {"role": "user", "content": None},
        ):
            with self.subTest(message=message), self.assertRaises(ValidationError):
                GeneratorRequest(model="z-ai/glm-5.3", messages=[message])

    async def test_http_errors_are_not_retried(self) -> None:
        for status in (401, 429, 500):
            with self.subTest(status=status):
                calls = []

                def handler(request: httpx.Request) -> httpx.Response:
                    calls.append(request)
                    return httpx.Response(status, json={"error": {"message": "failure"}})

                async with self.provider(handler) as provider:
                    with self.assertRaises(httpx.HTTPStatusError):
                        await provider.hit(MESSAGES)
                self.assertEqual(len(calls), 1)

    async def test_invalid_responses(self) -> None:
        for payload in (
            {},
            {"choices": []},
            {"error": {"message": "upstream failure"}},
            {"choices": [{"message": {"role": "assistant", "content": None}, "finish_reason": "stop"}]},
            {"choices": [{"message": {"role": "assistant", "content": "partial"}, "finish_reason": "length"}]},
            {"choices": [{"message": {"role": "assistant", "content": "filtered"}, "finish_reason": "content_filter"}]},
        ):
            with self.subTest(payload=payload):
                async with self.provider(lambda request: httpx.Response(200, json=payload)) as provider:
                    with self.assertRaises(ValidationError):
                        await provider.hit(MESSAGES)

    async def test_invalid_json(self) -> None:
        async with self.provider(lambda request: httpx.Response(200, text="invalid JSON")) as provider:
            with self.assertRaises(ValidationError):
                await provider.hit(MESSAGES)

    async def test_timeout_propagates(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Timed out", request=request)

        async with self.provider(handler) as provider:
            with self.assertRaises(httpx.ReadTimeout):
                await provider.hit(MESSAGES)
