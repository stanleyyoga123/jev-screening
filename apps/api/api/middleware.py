import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import request_id


logger = logging.getLogger("RequestLoggingMiddleware")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        identifier = uuid4().hex
        token = request_id.set(identifier)
        started = perf_counter()
        status = 500

        async def send_response(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = identifier
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            logger.exception("request_failed")
            raise
        finally:
            route = scope.get("fastapi", {}).get("effective_route_context", scope.get("route"))
            path = route.path if route else "<unmatched>"
            level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            logger.log(
                level,
                "request_completed method=%s route=%s status=%s duration_ms=%.1f",
                scope["method"], path, status, (perf_counter() - started) * 1000,
            )
            request_id.reset(token)
