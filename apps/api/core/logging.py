import logging
import logging.config
import traceback
from types import TracebackType
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from time import perf_counter


request_id: ContextVar[str] = ContextVar("request_id", default="-")


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        identifier = request_id.get()
        if identifier != "-":
            record = copy(record)
            record.msg = f"{record.getMessage()} request_id={identifier}"
            record.args = ()
        return super().format(record)

    def formatException(
        self, exc_info: tuple[type[BaseException], BaseException, TracebackType | None]
    ) -> str:
        # Exception messages, source lines, and locals can contain input or secrets.
        exception_type, _, trace = exc_info
        frames = traceback.extract_tb(trace)
        locations = "\n".join(
            f"  {frame.filename}:{frame.lineno} in {frame.name}" for frame in frames
        )
        return f"{exception_type.__name__}\n{locations}"


def configure_logging(level: str) -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "()": ConsoleFormatter,
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "console",
            },
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
            "uvicorn.error": {"handlers": [], "level": level, "propagate": True},
            # Our middleware logs route templates without raw URLs/query strings.
            "uvicorn.access": {"handlers": [], "propagate": False},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "pdfminer": {"level": "WARNING"},
            "python_multipart": {"level": "WARNING"},
        },
    })


@contextmanager
def log_operation(logger: logging.Logger, operation: str) -> Iterator[None]:
    started = perf_counter()
    logger.debug("operation_started operation=%s", operation)
    try:
        yield
    except Exception as exc:
        logger.warning(
            "operation_failed operation=%s error_type=%s duration_ms=%.1f",
            operation, type(exc).__name__, (perf_counter() - started) * 1000,
        )
        raise
    else:
        logger.info(
            "operation_completed operation=%s duration_ms=%.1f",
            operation, (perf_counter() - started) * 1000,
        )
