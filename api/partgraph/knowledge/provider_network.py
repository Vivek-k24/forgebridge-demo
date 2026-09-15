from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

Resolver = Callable[[str, int], Iterable[str]]

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.goog",
    }
)


class ProviderNetworkPolicyError(ValueError):
    """Raised when a provider URL or resolved target violates outbound policy."""


@dataclass(frozen=True, slots=True)
class ResolvedProviderTarget:
    """One validated connection target for a generic provider request.

    `resolved_addresses` is the approved address set for this connection attempt.
    A future network client must connect to one of these addresses instead of
    resolving the hostname again after validation; every retry and redirect must
    obtain a fresh target so DNS changes are checked again.
    """

    url: str
    hostname: str
    port: int
    resolved_addresses: tuple[str, ...]


def _blocked_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ProviderNetworkPolicyError("provider target resolved to an invalid IP address") from exc
    return not parsed.is_global


def _normalize_hostname(hostname: str) -> str:
    candidate = hostname.rstrip(".").casefold()
    if not candidate:
        raise ProviderNetworkPolicyError("provider URL hostname is required")
    try:
        normalized = candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ProviderNetworkPolicyError("provider URL hostname is invalid") from exc
    if len(normalized) > 253 or any(not label for label in normalized.split(".")):
        raise ProviderNetworkPolicyError("provider URL hostname is invalid")
    return normalized


def _validate_hostname_without_dns(hostname: str) -> None:
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise ProviderNetworkPolicyError("provider URL hostname is not an allowed outbound target")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return
    if _blocked_address(hostname):
        raise ProviderNetworkPolicyError("provider URL IP address is not publicly routable")


def normalize_provider_base_url(value: str) -> str:
    """Canonicalize a stored provider URL without performing DNS resolution."""

    cleaned = value.strip()
    if not cleaned:
        raise ProviderNetworkPolicyError("provider base URL cannot be blank")
    if any(character in cleaned for character in ("\\", "\r", "\n", "\t", "\x00")):
        raise ProviderNetworkPolicyError("provider base URL contains unsafe characters")

    try:
        parsed = urlsplit(cleaned)
        port = parsed.port
    except ValueError as exc:
        raise ProviderNetworkPolicyError("provider base URL is invalid") from exc

    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise ProviderNetworkPolicyError("provider base URL must use http or https")
    if not parsed.netloc or parsed.hostname is None:
        raise ProviderNetworkPolicyError("provider base URL hostname is required")
    if parsed.username is not None or parsed.password is not None:
        raise ProviderNetworkPolicyError("provider base URL must not include user information")
    if parsed.query or parsed.fragment:
        raise ProviderNetworkPolicyError("provider base URL must not include a query or fragment")

    hostname = _normalize_hostname(parsed.hostname)
    _validate_hostname_without_dns(hostname)

    if port is not None and not 1 <= port <= 65535:
        raise ProviderNetworkPolicyError("provider base URL port is invalid")

    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    rendered_port = "" if port is None or port == default_port else f":{port}"
    normalized = urlunsplit((scheme, f"{rendered_host}{rendered_port}", parsed.path, "", ""))
    return normalized.rstrip("/")


def _system_resolver(hostname: str, port: int) -> tuple[str, ...]:
    try:
        rows = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ProviderNetworkPolicyError("provider hostname could not be resolved") from exc
    addresses = {row[4][0] for row in rows}
    return tuple(sorted(addresses))


def resolve_provider_target(
    value: str,
    *,
    resolver: Resolver | None = None,
    allowed_hostnames: frozenset[str] | None = None,
) -> ResolvedProviderTarget:
    """Resolve and validate one outbound provider connection attempt.

    All resolved addresses must be globally routable. Rejecting the entire answer
    when any address is private prevents a mixed public/private DNS answer from
    becoming a route to an internal target.
    """

    normalized_url = normalize_provider_base_url(value)
    parsed = urlsplit(normalized_url)
    assert parsed.hostname is not None
    hostname = _normalize_hostname(parsed.hostname)

    if allowed_hostnames is not None:
        normalized_allowlist = frozenset(_normalize_hostname(item) for item in allowed_hostnames)
        if hostname not in normalized_allowlist:
            raise ProviderNetworkPolicyError("provider hostname is not allowed for this adapter")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    active_resolver = resolver or _system_resolver
    addresses = tuple(dict.fromkeys(active_resolver(hostname, port)))
    if not addresses:
        raise ProviderNetworkPolicyError("provider hostname resolved to no addresses")
    if any(_blocked_address(address) for address in addresses):
        raise ProviderNetworkPolicyError("provider hostname resolved to a non-public address")

    return ResolvedProviderTarget(
        url=normalized_url,
        hostname=hostname,
        port=port,
        resolved_addresses=addresses,
    )


def resolve_provider_redirect(
    current_url: str,
    location: str,
    *,
    resolver: Resolver | None = None,
    allowed_hostnames: frozenset[str] | None = None,
) -> ResolvedProviderTarget:
    """Validate a redirect before a generic provider client follows it."""

    if not location.strip():
        raise ProviderNetworkPolicyError("provider redirect location is empty")
    next_url = urljoin(current_url, location.strip())
    current = urlsplit(normalize_provider_base_url(current_url))
    redirected = urlsplit(next_url)
    if current.scheme == "https" and redirected.scheme.casefold() == "http":
        raise ProviderNetworkPolicyError("provider redirect cannot downgrade HTTPS to HTTP")
    return resolve_provider_target(
        next_url,
        resolver=resolver,
        allowed_hostnames=allowed_hostnames,
    )
