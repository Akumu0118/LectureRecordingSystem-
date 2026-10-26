from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, field_validator, model_validator


def no_controls(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Control characters are not allowed")
    return value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), AfterValidator(no_controls)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200), AfterValidator(no_controls)]


class LecturerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    department: OptionalText | None = None

    @field_validator("department")
    @classmethod
    def empty_department(cls, value):
        return value or None


class LecturerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    department: OptionalText | None = None

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("Name cannot be null")
        return value

    @field_validator("department")
    @classmethod
    def empty_department(cls, value):
        return value or None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide name or department to update")
        return self


class LecturerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    department: str | None
    created_at: datetime
    updated_at: datetime


class LecturerPage(BaseModel):
    items: list[LecturerRead]
    total: int
    limit: int
    offset: int
