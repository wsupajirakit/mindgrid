"""Request size caps (OWASP REST: limit request size): uploads get the intake limit, every
other request the general one. Checked on Content-Length and counted while streaming."""

import json
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mindgrid.core.config import AppSettings, env_field, settings_getter
from mindgrid.datasets import config as dataset_config
from mindgrid.knowledge.intake import config as intake_config

UPLOAD_SUFFIX = "/documents"
DATASET_UPLOAD = re.compile(r"^/v1/projects/[^/]+/datasets/[^/]+$")


class BodySettings(AppSettings):
    max_body_bytes: int = env_field(
        "MINDGRID_MAX_BODY_BYTES", 1024 * 1024, doc="Largest non-upload request body (bytes).", gt=0
    )


get_settings = settings_getter(BodySettings)


class _TooLargeError(Exception):
    pass


def _limit(scope: Scope) -> int:
    post, path = scope.get("method") == "POST", str(scope.get("path", ""))
    multipart_slack = 64 * 1024  # form boundaries and headers around the file
    if post and path.endswith(UPLOAD_SUFFIX):
        return intake_config.get_settings().max_upload_bytes + multipart_slack
    if post and DATASET_UPLOAD.match(path):
        return dataset_config.get_settings().max_bytes + multipart_slack
    return get_settings().max_body_bytes


async def _refuse(send: Send) -> None:
    body = json.dumps(
        {"error": {"code": "request.too_large", "message": "body too large", "params": {}}}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = _limit(scope)
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _refuse(send)
            return
        seen = 0

        async def counted() -> Message:
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > limit:
                raise _TooLargeError
            return message

        try:
            await self.app(scope, counted, send)
        except _TooLargeError:
            await _refuse(send)
