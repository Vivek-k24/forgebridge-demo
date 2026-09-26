import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from partgraph import config

REPO_ROOT = Path(__file__).resolve().parents[2]
VERCEL_CONFIG_PATH = REPO_ROOT / "api" / "vercel.json"


class AuthOriginTests(unittest.TestCase):
    def test_production_accepts_only_primary_origin(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERCEL": "1",
                "VERCEL_ENV": "production",
                "VERCEL_BRANCH_URL": "partgraph-preview.example.vercel.app",
                "VERCEL_URL": "partgraph-deployment.example.vercel.app",
            },
            clear=True,
        ):
            origins = config._allowed_web_origins("https://partgraph-main.vercel.app")

        self.assertEqual(origins, frozenset({"https://partgraph-main.vercel.app"}))

    def test_preview_accepts_only_exact_vercel_preview_origins(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERCEL": "1",
                "VERCEL_ENV": "preview",
                "VERCEL_BRANCH_URL": "partgraph-branch.example.vercel.app",
                "VERCEL_URL": "partgraph-deployment.example.vercel.app",
            },
            clear=True,
        ):
            origins = config._allowed_web_origins("https://partgraph-main.vercel.app")

        self.assertEqual(
            origins,
            frozenset(
                {
                    "https://partgraph-main.vercel.app",
                    "https://partgraph-branch.example.vercel.app",
                    "https://partgraph-deployment.example.vercel.app",
                }
            ),
        )
        self.assertNotIn("https://attacker.example", origins)

    def test_non_vercel_environment_does_not_expand_origins(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERCEL_ENV": "preview",
                "VERCEL_BRANCH_URL": "partgraph-branch.example.vercel.app",
            },
            clear=True,
        ):
            origins = config._allowed_web_origins("http://localhost:5173")

        self.assertEqual(origins, frozenset({"http://localhost:5173"}))

    def test_hosted_vercel_config_enforces_content_security_policy(self) -> None:
        payload = json.loads(VERCEL_CONFIG_PATH.read_text(encoding="utf-8"))
        header_rules = payload.get("headers", [])
        self.assertTrue(header_rules)

        csp_values = [
            header["value"]
            for rule in header_rules
            for header in rule.get("headers", [])
            if header.get("key", "").casefold() == "content-security-policy"
        ]
        self.assertEqual(len(csp_values), 1)
        csp = csp_values[0]

        required_directives = (
            "default-src 'self'",
            "connect-src 'self' https://vercel.live wss://ws-us3.pusher.com",
            "img-src 'self' https://vercel.live https://vercel.com data: blob:",
            "style-src 'self' https://vercel.live 'unsafe-inline'",
            "script-src 'self' https://vercel.live",
            "font-src 'self' https://vercel.live https://assets.vercel.com",
            "frame-src https://vercel.live",
            "object-src 'none'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        )
        for directive in required_directives:
            self.assertIn(directive, csp)

        self.assertNotIn("'unsafe-eval'", csp)
        script_src = next(
            directive.strip()
            for directive in csp.split(";")
            if directive.strip().startswith("script-src ")
        )
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("*", script_src)


if __name__ == "__main__":
    unittest.main()
