import base64
import json
import unittest
from dataclasses import replace
from uuid import uuid4

from cryptography.exceptions import InvalidTag

from partgraph.operator import credentials


class ProviderCredentialCryptoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_settings = credentials.settings
        key_v1 = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
        key_v2 = base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
        credentials.settings = replace(
            self.original_settings,
            provider_credential_keys=json.dumps({"1": key_v1, "2": key_v2}),
            provider_credential_active_key_version=2,
        )

    def tearDown(self) -> None:
        credentials.settings = self.original_settings

    def test_encrypts_and_round_trips_without_storing_plaintext(self) -> None:
        provider_id = uuid4()
        plaintext = "provider-access-key-ABCD"

        protected = credentials.protect_provider_credential(
            plaintext,
            provider_id=provider_id,
        )

        self.assertNotEqual(protected.ciphertext, plaintext.encode("utf-8"))
        self.assertEqual(protected.key_version, 2)
        self.assertEqual(protected.hint, "ABCD")
        self.assertEqual(len(protected.fingerprint), 64)
        self.assertEqual(
            credentials.reveal_provider_credential(
                ciphertext=protected.ciphertext,
                nonce=protected.nonce,
                key_version=protected.key_version,
                provider_id=provider_id,
            ),
            plaintext,
        )

    def test_ciphertext_is_bound_to_provider_identity(self) -> None:
        protected = credentials.protect_provider_credential(
            "provider-access-key-WXYZ",
            provider_id=uuid4(),
        )

        with self.assertRaises(credentials.ProviderCredentialError):
            credentials.reveal_provider_credential(
                ciphertext=protected.ciphertext,
                nonce=protected.nonce,
                key_version=protected.key_version,
                provider_id=uuid4(),
            )

    def test_missing_key_version_fails_closed(self) -> None:
        provider_id = uuid4()
        protected = credentials.protect_provider_credential(
            "provider-access-key-1234",
            provider_id=provider_id,
        )

        with self.assertRaises(credentials.ProviderCredentialError):
            credentials.reveal_provider_credential(
                ciphertext=protected.ciphertext,
                nonce=protected.nonce,
                key_version=99,
                provider_id=provider_id,
            )

    def test_missing_configuration_fails_closed(self) -> None:
        credentials.settings = replace(
            self.original_settings,
            provider_credential_keys=None,
            provider_credential_active_key_version=1,
        )

        with self.assertRaises(credentials.ProviderCredentialError):
            credentials.protect_provider_credential(
                "provider-access-key-FAIL",
                provider_id=uuid4(),
            )


if __name__ == "__main__":
    unittest.main()
