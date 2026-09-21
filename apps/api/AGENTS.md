# AGENTS.md

## Python Coding Guidelines

When writing or modifying Python code in this repository, prefer simple, strongly typed, explicit code over defensive runtime checks.

The codebase should rely on well-defined interfaces and Pydantic models for validation rather than repeatedly validating values inside application logic.

---

## 1. Use Modern Python

Use modern Python syntax and type annotations.

Prefer:

```python
def get_user(user_id: str) -> User:
    ...
```

instead of:

```python
def get_user(user_id):
    ...
```

Use modern union syntax:

```python
str | None
```

instead of:

```python
Optional[str]
```

Use built-in generic types:

```python
list[str]
dict[str, int]
```

instead of:

```python
List[str]
Dict[str, int]
```

---

## 2. Prefer Pydantic for Validation

Runtime data validation should generally happen through Pydantic models.

Do not manually validate structured input using repeated `isinstance`, `hasattr`, dictionary key checks, or similar defensive checks when the data can be represented as a Pydantic model.

Avoid:

```python
def process_user(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("data must be a dict")

    if "name" not in data:
        raise ValueError("name is required")

    if not isinstance(data["name"], str):
        raise ValueError("name must be a string")
```

Prefer:

```python
from pydantic import BaseModel


class User(BaseModel):
    name: str


def process_user(user: User) -> None:
    ...
```

When input originates from an untrusted boundary, validate it once:

```python
user = User.model_validate(payload)
process_user(user)
```

After a value has been validated into a Pydantic model, application code should trust the model.

Do not repeat validation such as:

```python
if not isinstance(user.name, str):
    ...
```

when `user` is already a validated `User`.

---

## 3. Validate at Boundaries

Validation should happen at system boundaries rather than throughout internal business logic.

Typical validation boundaries include:

* HTTP request payloads
* API responses from external services
* messages from queues or event systems
* database data when its shape cannot be guaranteed
* JSON/YAML configuration
* environment variables
* CLI input

Convert raw data into typed models as early as possible.

Prefer:

```python
payload = await response.json()
result = ExternalAPIResponse.model_validate(payload)

handle_result(result)
```

instead of passing raw dictionaries throughout the application:

```python
payload = await response.json()

if "result" not in payload:
    ...

handle_result(payload)
```

Internal functions should generally accept already validated objects.

---

## 4. Do Not Add Defensive `isinstance` Checks Without a Real Boundary

Avoid code like:

```python
if not isinstance(settings, Settings):
    raise TypeError("settings must be Settings")
```

when the function signature already establishes the expected contract:

```python
def create_client(settings: Settings) -> Client:
    ...
```

Type annotations define the interface.

If runtime validation is actually necessary, model the input using Pydantic rather than scattering manual type checks throughout the code.

`isinstance` is still acceptable when runtime type dispatch is genuinely part of the domain logic, for example:

```python
match event:
    case CreatedEvent():
        ...
    case DeletedEvent():
        ...
```

Do not use it merely to compensate for poorly defined interfaces.

---

## 5. Required Dependencies Should Be Required

Do not make dependencies optional merely to make construction more defensive.

Avoid:

```python
class APIClient:
    def __init__(
        self,
        settings: Settings | None = None,
    ):
        self.settings = settings or Settings()
```

Prefer:

```python
class APIClient:
    def __init__(
        self,
        settings: Settings,
    ):
        self.settings = settings
```

If a component requires configuration, require the caller to provide it.

This makes dependencies explicit and prevents hidden behaviour.

---

## 6. Do Not Silently Construct Configuration

Configuration should normally be created at the application's composition root and passed into components.

Prefer:

```python
settings = Settings()
client = APIClient(settings=settings)
service = UserService(client=client)
```

rather than:

```python
class APIClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
```

The component should not decide where its configuration comes from.

This makes:

* testing easier
* dependencies visible
* configuration predictable
* application startup failures easier to understand

---

## 7. Use Pydantic Settings for Configuration

For environment-based configuration, prefer `pydantic-settings`.

Example:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    api_url: str
    api_key: str
    timeout_seconds: float = Field(default=30.0, gt=0)
```

Required configuration should not receive arbitrary fallback values.

Avoid:

```python
api_key: str = ""
```

Prefer:

```python
api_key: str
```

If the application cannot operate correctly without a value, startup should fail clearly when that value is missing.

---

## 8. Avoid Unnecessary `None`

Do not use `None` simply because a value theoretically could be absent.

Use optional types only when absence is meaningful in the domain.

Avoid:

```python
def __init__(
    self,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
):
    ...
```

when both dependencies are required.

Prefer:

```python
def __init__(
    self,
    settings: Settings,
    client: httpx.AsyncClient,
):
    ...
```

If a dependency is deliberately optional, `None` is appropriate:

```python
def __init__(
    self,
    settings: Settings,
    cache: Cache | None = None,
):
    ...
```

but only when "no cache" is a supported application state.

---

## 9. Make Dependency Ownership Explicit

If a class receives a dependency, it should generally not unexpectedly replace or recreate it.

Prefer:

```python
class APIClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
    ) -> None:
        self.settings = settings
        self.client = client
```

If the class should own the HTTP client's lifecycle, make that design explicit rather than supporting both injected and internally constructed clients without a clear reason.

Avoid ambiguous patterns such as:

```python
self.client = client or httpx.AsyncClient()
```

unless supporting both behaviours is intentional and documented.

---

## 10. Prefer Explicit Interfaces

Functions and classes should clearly state what they require.

Prefer:

```python
async def screen_resume(
    resume: Resume,
    job: JobDescription,
    llm: LLMClient,
) -> ScreeningResult:
    ...
```

instead of:

```python
async def screen_resume(
    resume=None,
    job=None,
    llm=None,
):
    if resume is None:
        ...
```

Required values should be required by the interface.

---

## 11. Do Not Overuse `dict[str, Any]`

Avoid propagating loosely typed dictionaries through the application.

Avoid:

```python
def process_result(result: dict[str, Any]) -> dict[str, Any]:
    ...
```

Prefer:

```python
class ScreeningResult(BaseModel):
    score: float
    explanation: str


def process_result(result: ScreeningResult) -> ScreeningResult:
    ...
```

Use dictionaries when the structure is genuinely dynamic rather than simply because defining a model takes additional code.

---

## 12. Prefer Domain Models Over Primitive Containers

When a group of values represents a meaningful concept, create a model for it.

Instead of:

```python
def evaluate(
    candidate_name: str,
    candidate_email: str,
    candidate_skills: list[str],
    candidate_experience: int,
):
    ...
```

prefer:

```python
class Candidate(BaseModel):
    name: str
    email: str
    skills: list[str]
    experience_years: int


def evaluate(candidate: Candidate) -> Evaluation:
    ...
```

This keeps validation and domain structure centralized.

---

## 13. Do Not Catch Exceptions Without a Reason

Avoid broad exception handling such as:

```python
try:
    ...
except Exception:
    return None
```

This hides programming errors and makes debugging difficult.

Catch exceptions when you can meaningfully:

* recover
* translate them into a domain-specific error
* add useful context
* perform cleanup
* map them to an external protocol response

Prefer:

```python
try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    raise ExternalServiceError(
        f"External service returned {exc.response.status_code}"
    ) from exc
```

Do not catch an exception only to log it and continue as though the operation succeeded.

---

## 14. Fail Fast on Invalid State

Do not attempt to keep running with configuration or state that makes correct behaviour impossible.

For example, do not write:

```python
if not settings.api_key:
    logger.warning("API key missing")
```

and continue making API requests.

The configuration model should reject invalid configuration during startup.

```python
class Settings(BaseSettings):
    api_key: str = Field(min_length=1)
```

Prefer clear startup failures over delayed failures deep inside application logic.

---

## 15. Avoid Silent Fallbacks

Fallback behaviour should be intentional.

Avoid:

```python
timeout = settings.timeout or 30
```

if `timeout` is supposed to always exist.

Prefer defining the default where the configuration model is declared:

```python
class Settings(BaseSettings):
    timeout: float = 30.0
```

Then simply use:

```python
timeout = settings.timeout
```

The model should own defaults and validation.

---

## 16. Keep Functions Focused

Functions should perform one clear responsibility.

Avoid combining:

* validation
* HTTP calls
* parsing
* persistence
* business logic
* logging
* response formatting

inside one large function.

Prefer small functions with typed inputs and outputs.

For example:

```python
async def fetch_candidate(...) -> Candidate:
    ...

def evaluate_candidate(
    candidate: Candidate,
    criteria: list[Criterion],
) -> Evaluation:
    ...

async def save_evaluation(evaluation: Evaluation) -> None:
    ...
```

---

## 17. Prefer Early Returns Over Deep Nesting

Avoid:

```python
if user:
    if user.active:
        if user.subscription:
            return process(user)
```

Prefer:

```python
if not user.active:
    return None

if user.subscription is None:
    return None

return process(user)
```

However, do not add checks for impossible states when the type/model already guarantees them.

---

## 18. Use Clear Naming

Names should communicate intent rather than implementation details.

Prefer:

```python
screening_result
candidate
job_description
criteria
```

instead of:

```python
data
obj
result_dict
temp
x
```

Avoid unnecessary abbreviations unless they are established terms in the domain.

---

## 19. Keep Models Strict Where Appropriate

For internal or API contracts where unexpected fields likely indicate an error, prefer explicit Pydantic configuration.

Example:

```python
from pydantic import BaseModel, ConfigDict


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
```

This should be chosen based on the boundary.

For APIs that intentionally return additional fields, allowing or ignoring extra fields may be more appropriate.

---

## 20. Prefer Model Validators for Cross-Field Validation

Do not put cross-field validation into unrelated service logic.

Prefer:

```python
from pydantic import BaseModel, model_validator


class DateRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_range(self) -> "DateRange":
        if self.end <= self.start:
            raise ValueError("end must be after start")

        return self
```

Then application code can trust:

```python
date_range.end > date_range.start
```

without rechecking it.

---

## 21. Separate External Schemas From Domain Models When Necessary

Do not force an external API's awkward representation throughout the application.

Validate the external schema first, then map it into an internal model.

Example:

```python
class ExternalUserResponse(BaseModel):
    user_id: str
    display_name: str


class User(BaseModel):
    id: str
    name: str


def to_user(response: ExternalUserResponse) -> User:
    return User(
        id=response.user_id,
        name=response.display_name,
    )
```

Internal code should operate on domain models rather than external transport formats.

---

## 22. Prefer Dependency Injection Without Overengineering

Dependencies should generally be supplied explicitly.

```python
class ScreeningService:
    def __init__(
        self,
        repository: ScreeningRepository,
        llm: LLMClient,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.llm = llm
        self.settings = settings
```

Do not introduce dependency injection frameworks unless the project actually benefits from them.

Simple constructor injection is usually sufficient.

---

## 23. Testing

Tests should construct dependencies explicitly.

Prefer:

```python
settings = Settings(
    api_url="https://example.test",
    api_key="test-key",
)

service = ScreeningService(
    repository=fake_repository,
    llm=fake_llm,
    settings=settings,
)
```

instead of depending on hidden environment configuration inside the class under test.

Pydantic validation should also be tested at the model boundary rather than repeatedly testing impossible invalid states inside every service.

---

## 24. General Principle

The preferred flow is:

```text
raw external data
        ↓
Pydantic validation
        ↓
typed domain/application objects
        ↓
business logic
        ↓
typed result
```

Not:

```text
raw data
   ↓
manual check
   ↓
manual check
   ↓
isinstance
   ↓
key existence check
   ↓
fallback
   ↓
business logic
   ↓
more defensive checks
```

Once data has crossed a validated boundary, trust the contract.

Keep required dependencies required, make configuration explicit, fail early when the application is misconfigured, and avoid defensive code that exists only to protect against states the type system or Pydantic model already prevents.
