from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

ProviderKind = Literal["internal_data", "vehicle_data", "ai", "manufacturer"]
ProviderCredentialStorage = Literal["encrypted_database", "external_reference"]
OperatorAuditAction = Literal[
    "provider_created",
    "provider_updated",
    "provider_enabled",
    "provider_disabled",
    "provider_credential_saved",
    "provider_credential_removed",
]
PROVIDER_KEY_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,95}$"


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class ProviderCreate(BaseModel):
    provider_key: str = Field(min_length=2, max_length=96, pattern=PROVIDER_KEY_PATTERN)
    display_name: str = Field(min_length=1, max_length=160)
    provider_kind: ProviderKind
    base_url: str | None = Field(default=None, max_length=1024)
    enabled: bool = False
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    credential: SecretStr | None = Field(default=None)
    secret_ref: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("provider_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        cleaned = _clean_optional(value)
        if cleaned is not None and not cleaned.startswith(("https://", "http://")):
            raise ValueError("base_url must use http or https")
        return cleaned.rstrip("/") if cleaned else None

    @field_validator("secret_ref", "notes")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value()
        if not 4 <= len(raw) <= 8192:
            raise ValueError("credential must be 4-8192 characters")
        return value

    @field_validator("capabilities")
    @classmethod
    def clean_capabilities(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = value.strip().casefold().replace(" ", "_")
            if not item or len(item) > 64:
                raise ValueError("capability names must be 1-64 characters")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned

    @model_validator(mode="after")
    def one_credential_source(self):
        if self.credential is not None and self.secret_ref is not None:
            raise ValueError("credential and secret_ref cannot both be supplied")
        return self


class ProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = Field(default=None, max_length=1024)
    enabled: bool | None = None
    capabilities: list[str] | None = Field(default=None, max_length=32)
    credential: SecretStr | None = None
    clear_credential: bool = False
    secret_ref: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        cleaned = _clean_optional(value)
        if cleaned is not None and not cleaned.startswith(("https://", "http://")):
            raise ValueError("base_url must use http or https")
        return cleaned.rstrip("/") if cleaned else None

    @field_validator("secret_ref", "notes")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value()
        if not 4 <= len(raw) <= 8192:
            raise ValueError("credential must be 4-8192 characters")
        return value

    @field_validator("capabilities")
    @classmethod
    def clean_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned: list[str] = []
        for value in values:
            item = value.strip().casefold().replace(" ", "_")
            if not item or len(item) > 64:
                raise ValueError("capability names must be 1-64 characters")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned

    @model_validator(mode="after")
    def valid_credential_change(self):
        if self.credential is not None and self.clear_credential:
            raise ValueError("credential and clear_credential cannot both be supplied")
        if self.credential is not None and self.secret_ref is not None:
            raise ValueError("credential and secret_ref cannot both be supplied")
        return self


class ProviderRead(BaseModel):
    id: UUID
    provider_key: str
    display_name: str
    provider_kind: ProviderKind
    base_url: str | None
    enabled: bool
    capabilities: list[str]
    secret_configured: bool
    secret_storage: ProviderCredentialStorage | None
    secret_hint: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class OperatorAuditRead(BaseModel):
    id: UUID
    actor_user_id: UUID
    action: OperatorAuditAction
    target_type: str
    target_id: UUID
    event_data: dict[str, object]
    created_at: datetime
