import unittest

from pydantic import ValidationError

from partgraph.knowledge.provider_network import (
    ProviderNetworkPolicyError,
    normalize_provider_base_url,
    resolve_provider_redirect,
    resolve_provider_target,
)
from partgraph.operator.schemas import ProviderCreate, ProviderUpdate


def _public_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
    return ("1.1.1.1", "2606:4700:4700::1111")


class ProviderUrlConfigurationTests(unittest.TestCase):
    def test_public_base_url_is_canonicalized_without_dns(self) -> None:
        self.assertEqual(
            normalize_provider_base_url(" HTTPS://API.Example.COM:443/v1/ "),
            "https://api.example.com/v1",
        )
        provider = ProviderCreate(
            provider_key="fixture-provider",
            display_name="Fixture provider",
            provider_kind="vehicle_data",
            base_url="HTTPS://API.Example.COM:443/v1/",
        )
        self.assertEqual(provider.base_url, "https://api.example.com/v1")

    def test_configuration_rejects_literal_internal_and_metadata_targets(self) -> None:
        forbidden = (
            "http://127.0.0.1",
            "http://[::1]",
            "http://10.0.0.7",
            "http://172.16.0.7",
            "http://192.168.0.7",
            "http://169.254.169.254/latest/meta-data",
            "http://metadata.google.internal",
            "http://localhost:8000",
        )
        for base_url in forbidden:
            with self.subTest(base_url=base_url):
                with self.assertRaises(ValidationError):
                    ProviderCreate(
                        provider_key="fixture-provider",
                        display_name="Fixture provider",
                        provider_kind="vehicle_data",
                        base_url=base_url,
                    )

    def test_configuration_rejects_userinfo_and_ambiguous_base_urls(self) -> None:
        forbidden = (
            "https://user:secret@example.com",
            "file:///tmp/provider",
            "https://example.com/v1?next=http://127.0.0.1",
            "https://example.com/v1#fragment",
            "https://example.com\\@127.0.0.1",
        )
        for base_url in forbidden:
            with self.subTest(base_url=base_url):
                with self.assertRaises(ValidationError):
                    ProviderUpdate(base_url=base_url)


class ProviderExecutionNetworkPolicyTests(unittest.TestCase):
    def test_public_dns_answers_are_pinned_for_one_connection_attempt(self) -> None:
        target = resolve_provider_target(
            "https://api.example.com:443/v1?make=Fixture&year=2099",
            resolver=_public_resolver,
        )
        self.assertEqual(
            target.url,
            "https://api.example.com/v1?make=Fixture&year=2099",
        )
        self.assertEqual(target.hostname, "api.example.com")
        self.assertEqual(target.port, 443)
        self.assertEqual(
            target.resolved_addresses,
            ("1.1.1.1", "2606:4700:4700::1111"),
        )

    def test_private_dns_answer_is_rejected(self) -> None:
        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_target(
                "https://api.example.com",
                resolver=lambda _hostname, _port: ("10.20.30.40",),
            )

    def test_mixed_public_private_dns_answer_fails_closed(self) -> None:
        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_target(
                "https://api.example.com",
                resolver=lambda _hostname, _port: ("1.1.1.1", "192.168.50.2"),
            )

    def test_dns_rebinding_is_rechecked_on_every_connection_attempt(self) -> None:
        answers = iter((("1.1.1.1",), ("127.0.0.1",)))

        def changing_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
            return next(answers)

        first = resolve_provider_target(
            "https://api.example.com",
            resolver=changing_resolver,
        )
        self.assertEqual(first.resolved_addresses, ("1.1.1.1",))
        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_target(
                "https://api.example.com",
                resolver=changing_resolver,
            )

    def test_redirect_to_literal_internal_target_is_rejected(self) -> None:
        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_redirect(
                "https://api.example.com/v1?make=Fixture",
                "https://169.254.169.254/latest/meta-data",
                resolver=_public_resolver,
            )

    def test_redirect_dns_target_is_revalidated(self) -> None:
        def redirect_resolver(hostname: str, _port: int) -> tuple[str, ...]:
            if hostname == "redirect.example.com":
                return ("127.0.0.1",)
            return ("1.1.1.1",)

        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_redirect(
                "https://api.example.com/v1",
                "https://redirect.example.com/next",
                resolver=redirect_resolver,
            )

    def test_https_redirect_cannot_downgrade_to_http(self) -> None:
        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_redirect(
                "https://api.example.com/v1",
                "http://public.example.com/next",
                resolver=_public_resolver,
            )

    def test_high_trust_adapter_can_require_an_exact_hostname_allowlist(self) -> None:
        allowed = frozenset({"api.nhtsa.gov"})
        target = resolve_provider_target(
            "https://api.nhtsa.gov",
            resolver=_public_resolver,
            allowed_hostnames=allowed,
        )
        self.assertEqual(target.hostname, "api.nhtsa.gov")

        with self.assertRaises(ProviderNetworkPolicyError):
            resolve_provider_target(
                "https://example.com",
                resolver=_public_resolver,
                allowed_hostnames=allowed,
            )


if __name__ == "__main__":
    unittest.main()
