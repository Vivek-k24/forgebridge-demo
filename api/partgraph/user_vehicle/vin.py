import asyncio
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import status

from ..config import settings
from ..errors import ErrorCode, PartGraphError

VIN_TRANSLITERATION = {
    **{str(number): number for number in range(10)},
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "P": 7,
    "R": 9,
    "S": 2,
    "T": 3,
    "U": 4,
    "V": 5,
    "W": 6,
    "X": 7,
    "Y": 8,
    "Z": 9,
}
VIN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
MAX_PROVIDER_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    year: int
    make: str
    model: str
    trim: str | None
    body_style: str | None
    engine: str | None
    transmission: str | None
    drivetrain: str | None


def normalize_vin(value: str) -> str:
    return "".join(value.upper().split())


def expected_check_digit(vin: str) -> str:
    total = sum(
        VIN_TRANSLITERATION[character] * weight
        for character, weight in zip(vin, VIN_WEIGHTS, strict=True)
    )
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def validate_vin(value: str) -> str:
    vin = normalize_vin(value)
    if len(vin) != 17 or any(character not in VIN_TRANSLITERATION for character in vin):
        raise PartGraphError(
            code=ErrorCode.VIN_INVALID_FORMAT,
            message="VIN must contain 17 valid characters; I, O, and Q are not used.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if vin[8] != expected_check_digit(vin):
        raise PartGraphError(
            code=ErrorCode.VIN_CHECK_DIGIT_INVALID,
            message="VIN check digit is invalid.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return vin


def mask_vin(vin: str) -> str:
    return f"{'*' * 11}{vin[-6:]}"


def _text(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _engine(row: dict[str, object]) -> str | None:
    tokens: list[str] = []
    displacement = _text(row, "DisplacementL")
    if displacement:
        try:
            value = float(displacement)
        except ValueError:
            pass
        else:
            if value > 0:
                tokens.append(f"{value:g}L")

    cylinders = _text(row, "EngineCylinders")
    if cylinders:
        try:
            count = int(float(cylinders))
        except ValueError:
            pass
        else:
            if count > 0:
                tokens.append(f"{count} cylinder")

    fuel = _text(row, "FuelTypePrimary")
    electrification = _text(row, "ElectrificationLevel")
    combined = " ".join(filter(None, (fuel, electrification))).casefold()
    if "hybrid" in combined:
        tokens.append("Hybrid")
    elif "diesel" in combined:
        tokens.append("Diesel")
    elif "electric" in combined:
        tokens.append("Electric")

    return " ".join(tokens) or None


def _transmission(row: dict[str, object]) -> str | None:
    style = _text(row, "TransmissionStyle")
    speeds = _text(row, "TransmissionSpeeds")
    if not style:
        return None
    if speeds:
        try:
            count = int(float(speeds))
        except ValueError:
            count = 0
        if count > 0 and "continuously" not in style.casefold() and "cvt" not in style.casefold():
            return f"{count}-speed {style}"
    return style


def _drivetrain(row: dict[str, object]) -> str | None:
    drive = _text(row, "DriveType")
    if not drive:
        return None
    key = drive.casefold()
    if "front" in key or "fwd" in key:
        return "FWD"
    if "rear" in key or "rwd" in key:
        return "RWD"
    if "all wheel" in key or "all-wheel" in key or "awd" in key:
        return "AWD"
    if "4wd" in key or "4x4" in key or "four wheel" in key or "four-wheel" in key:
        return "4WD"
    return drive


def parse_nhtsa_payload(payload: object) -> ProviderIdentity:
    if not isinstance(payload, dict):
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_INVALID_RESPONSE,
            message="VIN decoder returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )
    results = payload.get("Results")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_INVALID_RESPONSE,
            message="VIN decoder returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    row = results[0]
    error_code = _text(row, "ErrorCode")
    if error_code:
        codes = {code.strip() for code in error_code.split(",") if code.strip()}
        if codes - {"0"}:
            raise PartGraphError(
                code=ErrorCode.VIN_DECODE_FAILED,
                message="VIN decoder could not resolve this VIN cleanly.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    year_text = _text(row, "ModelYear")
    make = _text(row, "Make")
    model = _text(row, "Model")
    if not year_text or not make or not model:
        raise PartGraphError(
            code=ErrorCode.VIN_DECODE_FAILED,
            message="VIN decoder did not return enough vehicle identity data.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        year = int(year_text)
    except ValueError as exc:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_INVALID_RESPONSE,
            message="VIN decoder returned an invalid model year.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        ) from exc

    return ProviderIdentity(
        year=year,
        make=make,
        model=model,
        trim=_text(row, "Trim"),
        body_style=_text(row, "BodyClass"),
        engine=_engine(row),
        transmission=_transmission(row),
        drivetrain=_drivetrain(row),
    )


def _fetch_sync(vin: str) -> object:
    endpoint = (
        f"{settings.nhtsa_base_url}/DecodeVinValuesExtended/{quote(vin, safe='')}?format=json"
    )
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "User-Agent": "PartGraph/0.4"},
    )
    try:
        with urlopen(request, timeout=settings.nhtsa_timeout_seconds) as response:
            if response.status != 200:
                raise PartGraphError(
                    code=ErrorCode.VIN_PROVIDER_UNAVAILABLE,
                    message="VIN decoder is temporarily unavailable.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    retryable=True,
                )
            body = response.read(MAX_PROVIDER_BYTES + 1)
    except TimeoutError as exc:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_TIMEOUT,
            message="VIN decoder timed out. Use vehicle details or try again.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            retryable=True,
        ) from exc
    except HTTPError as exc:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_UNAVAILABLE,
            message="VIN decoder is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        code = (
            ErrorCode.VIN_PROVIDER_TIMEOUT
            if isinstance(reason, TimeoutError)
            else ErrorCode.VIN_PROVIDER_UNAVAILABLE
        )
        http_status = (
            status.HTTP_504_GATEWAY_TIMEOUT
            if code == ErrorCode.VIN_PROVIDER_TIMEOUT
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise PartGraphError(
            code=code,
            message=(
                "VIN decoder timed out. Use vehicle details or try again."
                if code == ErrorCode.VIN_PROVIDER_TIMEOUT
                else "VIN decoder is temporarily unavailable."
            ),
            status_code=http_status,
            retryable=True,
        ) from exc

    if len(body) > MAX_PROVIDER_BYTES:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_INVALID_RESPONSE,
            message="VIN decoder response exceeded the allowed size.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_INVALID_RESPONSE,
            message="VIN decoder returned invalid JSON.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        ) from exc


async def decode_vin_values_extended(vin: str) -> ProviderIdentity:
    payload = await asyncio.to_thread(_fetch_sync, vin)
    return parse_nhtsa_payload(payload)
