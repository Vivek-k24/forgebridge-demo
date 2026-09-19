from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

CSRF_HEADER = "X-PartGraph-CSRF"
CSRF_VALUE = "1"
API_VERSION_HEADER = "X-PartGraph-API-Version"
EXPECTED_API_VERSION = "v1"

class HostedProofError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostedProofConfig:
    base_url: str
    access_url: str | None
    identifier: str
    password: str
    year: int
    make: str
    model: str


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HostedProofError(f"{name} is required")
    return value


def _config() -> HostedProofConfig:
    base_url = _required_env("PARTGRAPH_HOSTED_NHTSA_BASE_URL").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HostedProofError("PARTGRAPH_HOSTED_NHTSA_BASE_URL must be an absolute HTTPS URL")

    access_url = os.getenv("PARTGRAPH_HOSTED_NHTSA_ACCESS_URL", "").strip() or None
    if access_url is not None:
        access = urlsplit(access_url)
        if access.scheme != "https" or access.netloc != parsed.netloc:
            raise HostedProofError(
                "PARTGRAPH_HOSTED_NHTSA_ACCESS_URL must use HTTPS and the same host as the base URL"
            )

    try:
        year = int(_required_env("PARTGRAPH_HOSTED_NHTSA_YEAR"))
    except ValueError as exc:
        raise HostedProofError("PARTGRAPH_HOSTED_NHTSA_YEAR must be an integer") from exc

    make = _required_env("PARTGRAPH_HOSTED_NHTSA_MAKE")
    model = _required_env("PARTGRAPH_HOSTED_NHTSA_MODEL")

    return HostedProofConfig(
        base_url=base_url,
        access_url=access_url,
        identifier=_required_env("PARTGRAPH_HOSTED_OPERATOR_IDENTIFIER"),
        password=_required_env("PARTGRAPH_HOSTED_OPERATOR_PASSWORD"),
        year=year,
        make=make,
        model=model,
    )


class HostedClient:
    def __init__(self, config: HostedProofConfig) -> None:
        self.config = config
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def _request(
        self,
        path_or_url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        csrf: bool = False,
    ) -> tuple[int, Any]:
        url = (
            path_or_url
            if path_or_url.startswith(("https://", "http://"))
            else urljoin(f"{self.config.base_url}/", path_or_url.lstrip("/"))
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "PartGraph-Hosted-NHTSA-Proof/1.0",
        }
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            headers[CSRF_HEADER] = CSRF_VALUE

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read()
                api_version = response.headers.get(API_VERSION_HEADER)
                if "/api/" in url and api_version != EXPECTED_API_VERSION:
                    raise HostedProofError(
                        f"{method} {urlsplit(url).path} returned API version {api_version!r}"
                    )
                parsed: Any = None
                if raw:
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise HostedProofError(
                            f"{method} {urlsplit(url).path} did not return valid JSON"
                        ) from exc
                return response.status, parsed
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise HostedProofError(
                f"{method} {urlsplit(url).path} returned HTTP {exc.code}: {raw[:500]}"
            ) from exc
        except URLError as exc:
            raise HostedProofError(
                f"{method} {urlsplit(url).path} could not reach the hosted Preview"
            ) from exc

    def prime_access(self) -> None:
        target = self.config.access_url or self.config.base_url
        request = Request(
            target,
            headers={"User-Agent": "PartGraph-Hosted-NHTSA-Proof/1.0"},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                response.read(1)
        except (HTTPError, URLError) as exc:
            raise HostedProofError("could not establish access to the hosted Preview") from exc

    def login(self) -> None:
        status, body = self._request(
            "/api/v1/auth/login",
            method="POST",
            payload={
                "identifier": self.config.identifier,
                "password": self.config.password,
            },
            csrf=True,
        )
        if status != 200 or not isinstance(body, dict) or "user" not in body:
            raise HostedProofError("operator login did not return an authenticated user")

    def logout(self) -> None:
        try:
            self._request("/api/v1/auth/logout", method="POST", csrf=True)
        except HostedProofError:
            pass


def _list(client: HostedClient, path: str) -> list[dict[str, Any]]:
    status, body = client._request(path)
    if status != 200 or not isinstance(body, list):
        raise HostedProofError(f"{path} did not return a list")
    if not all(isinstance(item, dict) for item in body):
        raise HostedProofError(f"{path} returned a malformed list")
    return body


def _find_nhtsa_binding(client: HostedClient) -> dict[str, Any]:
    status, access = client._request("/api/v1/operator/access")
    if status != 200 or not isinstance(access, dict):
        raise HostedProofError("authenticated account is not an operator administrator")

    providers = _list(client, "/api/v1/operator/providers")
    nhtsa_provider_ids = {
        str(provider["id"])
        for provider in providers
        if provider.get("provider_kind") == "vehicle_data"
        and provider.get("enabled") is True
        and str(provider.get("base_url") or "").rstrip("/") == "https://api.nhtsa.gov"
    }
    if not nhtsa_provider_ids:
        raise HostedProofError("no enabled api.nhtsa.gov vehicle-data provider exists in Preview")

    bindings = _list(client, "/api/v1/operator/provider-source-bindings")
    candidates = [
        binding
        for binding in bindings
        if str(binding.get("provider_connection_id")) in nhtsa_provider_ids
        and binding.get("source_key") == "nhtsa-recalls"
        and binding.get("ready_for_ingestion") is True
    ]
    if len(candidates) != 1:
        raise HostedProofError(
            f"expected exactly one ready NHTSA provider/source binding, found {len(candidates)}"
        )
    return candidates[0]


def _matching_audit_ids(
    events: list[dict[str, Any]],
    *,
    binding_id: str,
    config: HostedProofConfig,
) -> set[str]:
    ids: set[str] = set()
    for event in events:
        data = event.get("event_data")
        if (
            event.get("action") == "nhtsa_recall_query_staged"
            and str(event.get("target_id")) == binding_id
            and isinstance(data, dict)
            and data.get("year") == config.year
            and data.get("make") == config.make
            and data.get("model") == config.model
            and data.get("publication_mode") == "pending_candidates_only"
        ):
            ids.add(str(event.get("id")))
    return ids


def _run(config: HostedProofConfig) -> None:
    client = HostedClient(config)
    client.prime_access()
    client.login()

    try:
        binding = _find_nhtsa_binding(client)
        binding_id = str(binding["id"])
        audit_before = _matching_audit_ids(
            _list(client, "/api/v1/operator/audit"),
            binding_id=binding_id,
            config=config,
        )

        status, result = client._request(
            "/api/v1/operator/nhtsa/recalls/stage",
            method="POST",
            payload={
                "binding_id": binding_id,
                "year": config.year,
                "make": config.make,
                "model": config.model,
            },
            csrf=True,
        )
        if status != 200 or not isinstance(result, dict):
            raise HostedProofError("NHTSA operator stage endpoint did not return a result")

        if str(result.get("binding_id")) != binding_id:
            raise HostedProofError("NHTSA result used a different provider/source binding")
        if result.get("year") != config.year:
            raise HostedProofError("NHTSA result returned the wrong vehicle year")
        if result.get("make") != config.make or result.get("model") != config.model:
            raise HostedProofError("NHTSA result returned the wrong vehicle make/model")

        candidate_count = result.get("candidate_count")
        inserted_count = result.get("inserted_count")
        staging_ids = result.get("staging_record_ids")
        batch_id = result.get("ingestion_batch_id")
        if not isinstance(candidate_count, int) or candidate_count <= 0:
            raise HostedProofError("live NHTSA invocation returned no recall candidates")
        if not isinstance(inserted_count, int) or not 0 <= inserted_count <= candidate_count:
            raise HostedProofError("live NHTSA invocation returned an invalid inserted_count")
        if not isinstance(staging_ids, list) or len(staging_ids) != candidate_count:
            raise HostedProofError("candidate_count does not match staging_record_ids")
        if not isinstance(batch_id, str) or not batch_id:
            raise HostedProofError("live NHTSA invocation did not return an ingestion batch id")

        audit_after = _matching_audit_ids(
            _list(client, "/api/v1/operator/audit"),
            binding_id=binding_id,
            config=config,
        )
        if not audit_after.difference(audit_before):
            raise HostedProofError("live NHTSA invocation did not create a new operator audit event")

        print(
            "Hosted NHTSA ingestion proof passed: deployed Preview operator endpoint reached "
            "api.nhtsa.gov, staged "
            f"{candidate_count} pending candidate(s) in batch {batch_id}, "
            f"inserted {inserted_count}, and recorded a new operator audit event."
        )
    finally:
        client.logout()


def main() -> None:
    try:
        _run(_config())
    except HostedProofError as exc:
        print(f"Hosted NHTSA ingestion proof failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
