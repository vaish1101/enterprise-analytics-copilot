from __future__ import annotations

import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse


LOGGER = logging.getLogger("enterprise_analytics.api.errors")


class ProductError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def product_error_handler(request: Request, exc: ProductError) -> JSONResponse:
    LOGGER.warning(json.dumps({
        "event": "product_error", "request_id": getattr(request.state, "request_id", None),
        "error_class": type(exc).__name__, "error_code": exc.code,
    }, sort_keys=True))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "request_id": getattr(request.state, "request_id", None)}},
    )


async def safe_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.error(json.dumps({
        "event": "unhandled_error", "request_id": getattr(request.state, "request_id", None),
        "error_class": type(exc).__name__,
    }, sort_keys=True))
    return JSONResponse(
        status_code=500,
        content={"error": {
            "code": "INTERNAL_ERROR",
            "message": "The governed service failed safely. No unverified answer was released.",
            "request_id": getattr(request.state, "request_id", None),
        }},
    )
