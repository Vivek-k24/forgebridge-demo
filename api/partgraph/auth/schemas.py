from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class AuthResult(BaseModel):
    user: UserRead


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    units: Literal["us_customary", "metric"]


class PreferenceUpdate(BaseModel):
    units: Literal["us_customary", "metric"]
