"""Limit multipart bodies before the framework can spool unlimited input."""

import re

from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.core.config import get_settings


class ReferenceUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        if re.fullmatch(r"/api/lecturers/[^/]+/samples/?", scope["path"]):
            maximum = get_settings().max_reference_size_bytes + 64 * 1024
        elif re.fullmatch(r"/api/recordings/[^/]+/audio/?", scope["path"]):
            maximum = get_settings().max_recording_size_bytes + 64 * 1024
        else:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
        if size > maximum:
            return await JSONResponse({"detail": "Audio upload request is too large"}, status_code=413)(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > maximum:
                raise HTTPException(413, "Audio upload request is too large")
            return message

        await self.app(scope, bounded_receive, send)
