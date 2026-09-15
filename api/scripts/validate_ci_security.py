from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
SHA_REF = re.compile(r"^[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")


def _workflow_files() -> list[Path]:
    return sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))


def _external_action_refs(path: Path, text: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for match in USES_LINE.finditer(text):
        value = match.group(1)
        if value.startswith("./") or value.startswith("docker://"):
            continue
        if "@" not in value:
            raise SystemExit(f"{path}: external action reference has no immutable ref: {value}")
        action, ref = value.rsplit("@", 1)
        refs.append((action, ref))
    return refs


def _jobs(text: str) -> dict[str, str]:
    lines = text.splitlines()
    in_jobs = False
    current_name: str | None = None
    current_lines: list[str] = []
    jobs: dict[str, str] = {}

    for line in lines:
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        match = JOB_HEADER.match(line)
        if match:
            if current_name is not None:
                jobs[current_name] = "\n".join(current_lines)
            current_name = match.group(1)
            current_lines = [line]
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        jobs[current_name] = "\n".join(current_lines)
    return jobs


def validate() -> None:
    workflow_files = _workflow_files()
    if not workflow_files:
        raise SystemExit("no GitHub Actions workflows found")

    package_write_locations: list[tuple[str, str]] = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        for action, ref in _external_action_refs(path, text):
            if not SHA_REF.fullmatch(ref):
                raise SystemExit(
                    f"{path}: {action} must be pinned to a full 40-character commit SHA, got {ref!r}"
                )

        before_jobs = text.split("\njobs:\n", 1)[0]
        if "packages: write" in before_jobs:
            raise SystemExit(f"{path}: workflow-level packages: write is prohibited")

        for job_name, body in _jobs(text).items():
            if "packages: write" in body:
                package_write_locations.append((path.name, job_name))
                if path.name not in {"api.yml", "web.yml"} or job_name != "publish":
                    raise SystemExit(
                        f"{path}: packages: write is allowed only on the publish job"
                    )

    expected = {("api.yml", "publish"), ("web.yml", "publish")}
    actual = set(package_write_locations)
    if actual != expected:
        raise SystemExit(
            f"packages: write locations differ from policy: expected {sorted(expected)}, got {sorted(actual)}"
        )

    dependabot = DEPENDABOT_PATH.read_text(encoding="utf-8")
    required_fragments = (
        'package-ecosystem: "github-actions"',
        'directory: "/"',
        'interval: "weekly"',
    )
    missing = [fragment for fragment in required_fragments if fragment not in dependabot]
    if missing:
        raise SystemExit(f"Dependabot GitHub Actions policy is incomplete: missing {missing}")


if __name__ == "__main__":
    validate()
    print("GitHub Actions supply-chain policy validated.")
