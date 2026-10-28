"""API errors carry a stable code (translated by the web) next to an English message.

    raise ApiError(404, "project.not_found", "project not found", params={"id": pid})
    -> 404 {"error": {"code": "project.not_found", "message": "...", "params": {...}}}

Codes are dotted lowercase (`<module>.<reason>`); the web maps each to a message key.
"""

import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not CODE_PATTERN.fullmatch(code):
            raise ValueError(f"error code must be dotted lowercase, got {code!r}")
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.params = params or {}
        self.headers = headers


def _body(code: str, message: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "params": params}}


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)  # noqa: S101 — registered for ApiError only
    return JSONResponse(
        _body(exc.code, exc.message, exc.params), status_code=exc.status, headers=exc.headers
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    fields = [".".join(str(p) for p in err.get("loc", ())) for err in exc.errors()]
    return JSONResponse(
        _body("request.invalid", "request validation failed", {"fields": fields}),
        status_code=422,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
