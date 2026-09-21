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

## Console logging

Logs go to stdout using Python's standard `logging` module. Set `LOG_LEVEL` in
`.env` or the environment to `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, or
`CRITICAL`. Logging setup does not require provider credentials.

The format is `%(asctime)s | %(levelname)s | %(name)s | %(message)s`.
Logger names identify components such as `GeneratorProvider`, `CriteriaService`,
and `RequestLoggingMiddleware`. Request IDs are appended to messages during a request. Request
logs include the route template, method, status, and duration. Integration and PDF
extraction logs include operation timings and failure types; criteria generation
also reports the number of generated questions. Startup and shutdown are logged.
Responses passing through the middleware include an `X-Request-ID` header for
matching them to console output.

Application logs omit request/response bodies, query strings, authorization
headers, filenames, prompts, and extracted text. Unexpected exceptions include
their type and stack locations, without exception messages, source lines, or
locals. Uvicorn's raw access logger is replaced by the request middleware logger;
HTTP and PDF library debug output is suppressed. No log files are created.

Use `logging.getLogger("ClassName")` or a descriptive component name in new modules. Log operation metadata rather
than input or generated content.

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
integrations/               Jev client and transport schemas, and PDF reader
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
| `POST /api/criteria/generate` | Generates validated Jev questions from a job description |
| `POST /api/criteria/validate` | Returns 501 |
| `GET /api/criteria/prompt` | Returns the generation system prompt |
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

## Criteria generation

`POST /api/criteria/generate` accepts a JSON job description (1–30,000 characters,
with nonblank text) and uses the configured generator to create job-related Jev
Choice questions:

```sh
curl http://localhost:8000/api/criteria/generate \
  -H 'Content-Type: application/json' \
  -d '{"job_description":"Required: professional Python development experience."}'
```

```json
{
  "success": true,
  "data": {
    "questions": {
      "role_python": {
        "type": "choice",
        "instructions": "Does the resume document professional Python development experience?",
        "criteria": {
          "meets": "Professional Python development experience is explicitly documented.",
          "partial": "Only some relevant experience is documented.",
          "does_not_meet": "Explicit evidence establishes a shortfall.",
          "insufficient_evidence": "The resume does not establish the requirement."
        }
      }
    }
  }
}
```

`data.questions` can be passed as the `questions` argument to Jev. Generation
does not submit a resume to Jev or screen a candidate. The system prompt lives in
`domains/criteria/prompt.py`; `GET /api/criteria/prompt` returns it in
`StandardResponse[str]` without calling a provider.

Generated output is validated as 1–20 named Choice questions with the four
outcomes shown above. The prompt requires requirements grounded in the supplied
JD and preserves alternatives and required/preferred wording. Schema validation
checks structure; review the generated requirements before screening.

Invalid requests return 422. Invalid or empty generated questions and upstream
failures return 502; provider timeouts return 504. Provider output is not echoed
in error responses. The factory closes the generation client after each request;
there are no automatic retries or stored results. `/criteria/validate` remains
an unimplemented placeholder.

```sh
python -m unittest discover -s tests -p test_criteria.py -v
```

## Generator through OpenRouter

`integrations.generator.GeneratorProvider` calls OpenRouter's
`/api/v1/chat/completions` endpoint using `GENERATOR_MODEL` (default:
`z-ai/glm-5.3`). It shares `OPENROUTER_API_KEY` and
`PROVIDER_TIMEOUT_SECONDS` with Jev. This integration accepts text messages;
criteria prompts and generated-question validation belong to the criteria domain.

```python
from config.settings import Settings
from integrations.generator import GeneratorMessage, GeneratorProvider


async def generate(job_description: str) -> str:
    generator = GeneratorProvider(Settings())
    try:
        result = await generator.hit([
            GeneratorMessage(role="system", content="Extract job requirements from the supplied text."),
            GeneratorMessage(role="user", content=job_description),
        ])
        return result.content
    finally:
        await generator.aclose()
```

The provider creates and reuses its HTTP client. Responses are validated with
Pydantic; empty, truncated, or filtered completions are rejected. `result.content`
contains the first completed answer, and `result.model_dump()` includes top-level
metadata such as model and usage when returned. HTTP errors and timeouts propagate
without retries. No paid requests are made by the mocked tests:

```sh
python -m unittest discover -s tests -p test_generator.py -v
```

See [GLM 5.3 on OpenRouter](https://openrouter.ai/z-ai/glm-5.3) and
[OpenRouter's chat API quickstart](https://openrouter.ai/docs/quickstart).

## Jev through OpenRouter

```python
import asyncio

from config.settings import Settings
from integrations.jev import JevProvider


async def main():
    settings = Settings()
    async with JevProvider(settings) as provider:
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
creates and reuses its own HTTP client. Use `async with JevProvider(settings)`
to close it automatically, or call `await provider.aclose()` when finished.

Run mocked tests without an API key or paid requests:

```sh
python -m unittest discover -s tests -v
```
