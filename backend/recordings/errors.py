"""Consistent JSON errors: {"error": "<friendly message>", "code": "<machine_code>"}."""
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class ApiError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Request failed."
    default_code = "error"

    def __init__(self, message, code="error", status_code=None):
        super().__init__(detail=message, code=code)
        self.code = code
        if status_code is not None:
            self.status_code = status_code


def _first_message(data):
    if isinstance(data, dict):
        for value in data.values():
            return _first_message(value)
    if isinstance(data, (list, tuple)) and data:
        return _first_message(data[0])
    return str(data)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ApiError):
        response.data = {"error": str(exc.detail), "code": exc.code}
    elif isinstance(exc, ValidationError):
        response.data = {
            "error": _first_message(response.data),
            "code": "validation_error",
            "fields": response.data,
        }
    else:
        response.data = {
            "error": _first_message(response.data),
            "code": getattr(exc, "default_code", "error"),
        }
    return response
