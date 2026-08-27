from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_]+$"


class RegistrationInput(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.casefold()


class LoginInput(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().casefold()


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    created_at: datetime


class AuthResult(BaseModel):
    user: UserRead


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    units: Literal["us_customary", "metric"]


class PreferenceUpdate(BaseModel):
    units: Literal["us_customary", "metric"]
