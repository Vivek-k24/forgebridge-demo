import os
import unittest
from unittest.mock import patch

from partgraph import config


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


if __name__ == "__main__":
    unittest.main()
