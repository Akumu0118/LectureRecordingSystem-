"""File responses with HTTP Range support (needed for seeking in <audio>, esp. Safari)."""
import os
import re

from django.http import HttpResponse, StreamingHttpResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _iter_range(path, start, length, chunk=64 * 1024):
    with open(path, "rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def file_response(request, path, content_type, download_name=None):
    size = os.path.getsize(path)
    start, end, status = 0, size - 1, 200

    match = _RANGE_RE.fullmatch(request.headers.get("Range", "").strip())
    if match and (match.group(1) or match.group(2)):
        if match.group(1):
            start = int(match.group(1))
            if match.group(2):
                end = min(int(match.group(2)), size - 1)
        else:  # suffix range: last N bytes
            start = max(size - int(match.group(2)), 0)
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        status = 206

    length = end - start + 1
    response = StreamingHttpResponse(
        _iter_range(path, start, length), status=status, content_type=content_type
    )
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    if download_name:
        response["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response
