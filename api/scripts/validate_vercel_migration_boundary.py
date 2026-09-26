from __future__ import annotations

from pathlib import Path
import tomllib


API_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = API_ROOT / "pyproject.toml"


def main() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    try:
        build_script = data["tool"]["vercel"]["scripts"]["build"]
    except KeyError as exc:
        raise SystemExit(f"Missing Vercel build-script configuration: {exc}") from exc

    if not isinstance(build_script, str) or not build_script.strip():
        raise SystemExit("Vercel build script must remain an explicit non-empty command.")

    forbidden_markers = (
        "alembic",
        "upgrade head",
        "PARTGRAPH_DATABASE_URL",
        "PARTGRAPH_ALLOW_DATABASE_MIGRATION",
    )
    present = [marker for marker in forbidden_markers if marker in build_script]
    if present:
        raise SystemExit(
            "Vercel build must be schema-read-only; database migration marker(s) found: "
            + ", ".join(present)
        )

    required_markers = (
        "test_equipment_catalog_seed.py",
        "npm --prefix ../web ci",
        "npm --prefix ../web run build",
        "cp -R ../web/dist/. partgraph/frontend/",
    )
    missing = [marker for marker in required_markers if marker not in build_script]
    if missing:
        raise SystemExit(
            "Vercel build lost required application-build behavior: " + ", ".join(missing)
        )

    print("Vercel database-migration boundary passed: application build is schema-read-only.")


if __name__ == "__main__":
    main()
