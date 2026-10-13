"""Sanitised request lifecycle logging for the public API."""

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("app.http")
request_id_context: ContextVar[str] = ContextVar("request_id", default="UNKNOWN")


def current_request_id() -> str:
    """Return the request id for a lifecycle event without retaining request data."""
    return request_id_context.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log routing facts only; never headers, query values, or request bodies."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request_id_token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_request request_id=%s method=%s endpoint=%s status=%s duration_ms=%s",
                request_id, request.method, request.url.path, response.status_code, elapsed_ms,
            )
            return response
        finally:
            request_id_context.reset(request_id_token)
