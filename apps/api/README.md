# Backend

Run Python commands from `apps/api`. Install `requirements.txt` in a virtual
environment and set `OPENROUTER_API_KEY` in the environment or this directory's
`.env` file. See `.env.example` for optional settings.

## FastAPI application

From `apps/api`, start the development server:

```sh
uvicorn main:app --reload
```

Open `/docs` for Swagger UI or `/openapi.json` for the API schema.
The scaffold starts without provider credentials; provider configuration is
required when integrating the unfinished services.

```text
main.py                     ASGI entry point (main:app)
api/
  application.py            FastAPI factory and exception handlers
  router.py                 Registers feature routers under /api
config/                     Environment settings
core/                       Shared application contracts and errors
domains/
  health/
  documents/
  criteria/
  screening/
    factory.py              Constructs the feature's service dependencies
    model.py                Domain entities and business rules
    repository.py           Data access contracts (placeholder; no persistence)
    router.py               HTTP endpoints wired to the feature factory
    schema.py               Request and response validation schemas
    service.py              Application operations
integrations/               OpenRouter, Jev transport schemas, and PDF reader
utility/                    Shared helpers as needed
```

Every feature has all six modules shown under `screening`, plus `__init__.py`.
Routers resolve their service through the feature's factory using FastAPI
`Depends`. Services remain independent of FastAPI. Repository and unused model
or schema modules are placeholders until their contracts are implemented.
Add new features under `domains` and register their router in `api/router.py`.

| Endpoint | Scaffold behavior |
| --- | --- |
| `GET /api/health` | Returns `{"status": "ok"}` |
| `POST /api/documents/parse` | Extracts an uploaded PDF into `StandardResponse[str]` |
| `POST /api/criteria/generate` | Returns 501 |
| `POST /api/criteria/validate` | Returns 501 |
| `GET /api/criteria/prompt` | Returns 501 |
| `POST /api/screen` | Returns 501 |

Unfinished services raise `FeatureNotImplementedError`, mapped to HTTP 501 by
the application. These placeholder routes have no request bodies yet and do not
call providers. Set their success status and response model when implementing them.

## PDF upload

`POST /api/documents/parse` accepts a required multipart upload named `file`
with content type `application/pdf`. The documents router calls its service,
which extracts text with `PdfReader` in a worker thread.

```sh
curl http://localhost:8000/api/documents/parse \
  -F 'file=@resume.pdf;type=application/pdf'
```

The response uses the shared `StandardResponse` with string data:

```json
{"success": true, "data": "Extracted PDF text"}
```

Pages with text are joined with a blank line. PDFs without extractable text
return an empty string; OCR is not performed. Missing files and unreadable PDFs
return 422; unsupported content types return 415. The upload is closed after
reading. The application does not save the document or extracted text; multipart
uploads may be spooled to a temporary file by the framework.

Install `requirements.txt` for `pdfplumber` and `python-multipart`, then run the
document tests from `apps/api`:

```sh
python -m unittest discover -s tests -p test_documents.py -v
```

## Jev through OpenRouter

```python
import asyncio

from config.settings import Settings
from integrations.openrouter import OpenRouterProvider


async def main():
    settings = Settings()
    async with OpenRouterProvider(settings) as provider:
        result = await provider.hit(
            state="The resume describes three years building Python APIs.",
            questions={
                "python_experience": {
                    "type": "choice",
                    "instructions": "Does the resume document Python API experience?",
                    "criteria": {
                        "evidenced": "Python API experience is explicitly described.",
                        "unknown": "The resume does not establish this experience.",
                    },
                }
            },
        )
    return result.answers


answers = asyncio.run(main())
```

`hit` submits `model`, `state`, and a named `questions` map to OpenRouter's
`/api/alpha/decisions` endpoint. It returns a validated `JevResponse`; use
`result.answers` to read answers or `result.model_dump()` for the full response,
including provider usage metadata. Choice, Score, and Noul questions are supported.
The endpoint is experimental; its integration should be checked when upgrading.
See [OpenRouter's Jev lab](https://openrouter.ai/labs/jev).

Inputs are validated before sending. HTTP status errors and transport/timeouts
propagate as httpx exceptions. Malformed JSON or an invalid response shape raises
Pydantic `ValidationError`; missing requested answer keys raise `ValueError`.
Do not log exception request bodies or authentication headers. The provider does
not persist or log requests/results. Callers supply `Settings`; the provider
creates and reuses its own HTTP client. Use `async with OpenRouterProvider(settings)`
to close it automatically, or call `await provider.aclose()` when finished.

Run mocked tests without an API key or paid requests:

```sh
python -m unittest discover -s tests -v
```
