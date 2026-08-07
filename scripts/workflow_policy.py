#!/usr/bin/env python3
"""Read-only security policy checks for repository GitHub Actions workflows."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
EXPRESSION = "$" + "{{"
FORBIDDEN_TRIGGERS = {
    "pull_request_target",
    "repository_dispatch",
    "workflow_run",
}
FORBIDDEN_TOKEN_REFERENCES = (
    "secr" + "ets.",
    "github." + "token",
)
REQUIRED_SHELL = "shell: bash --noprofile --norc -euo pipefail {0}"


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def top_level_permissions(lines: list[str]) -> list[str] | None:
    for index, line in enumerate(lines):
        if line == "permissions:":
            values: list[str] = []
            for child in lines[index + 1 :]:
                if not child.strip() or child.lstrip().startswith("#"):
                    continue
                if indentation(child) == 0:
                    break
                values.append(child.strip())
            return values
        if line.startswith("permissions:"):
            return [line.partition(":")[2].strip()]
    return None


def check_run_expressions(path: Path, lines: list[str], errors: list[str]) -> None:
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)run:\s*(.*)$", line)
        if not match:
            continue

        run_indent = len(match.group(1))
        value = match.group(2)
        if EXPRESSION in value:
            errors.append(
                f"{path.name}:{index + 1}: GitHub expression must be passed through env, not expanded directly in run"
            )

        if value not in {"|", ">", "|-", ">-"}:
            continue

        for child_index in range(index + 1, len(lines)):
            child = lines[child_index]
            if not child.strip():
                continue
            if indentation(child) <= run_indent:
                break
            if EXPRESSION in child:
                errors.append(
                    f"{path.name}:{child_index + 1}: GitHub expression must be passed through env, not expanded directly in run"
                )


def check_workflow(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    permissions = top_level_permissions(lines)
    if permissions != ["contents: read"]:
        errors.append(
            f"{path.name}: top-level permissions must be exactly 'contents: read'"
        )

    if REQUIRED_SHELL not in {line.strip() for line in lines}:
        errors.append(
            f"{path.name}: hardened bash shell default is required"
        )

    if not any(line.strip().startswith("timeout-minutes:") for line in lines):
        errors.append(f"{path.name}: every workflow must define a job timeout")

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        key = stripped.removeprefix("- ")

        if key.startswith("uses:"):
            errors.append(
                f"{path.name}:{index}: actions and reusable workflows are not allowed; use repository code and standard runner tools"
            )

        for trigger in FORBIDDEN_TRIGGERS:
            if re.match(rf"^{re.escape(trigger)}\s*:", key):
                errors.append(
                    f"{path.name}:{index}: forbidden high-risk trigger: {trigger}"
                )

        lowered = line.lower()
        for fragment in FORBIDDEN_TOKEN_REFERENCES:
            if fragment in lowered:
                errors.append(
                    f"{path.name}:{index}: workflows must not reference secrets or the implicit GitHub token"
                )
                break

        if re.match(r"^continue-on-error\s*:\s*true\s*$", key, flags=re.IGNORECASE):
            errors.append(
                f"{path.name}:{index}: security and validation steps must not silently continue on error"
            )

    check_run_expressions(path, lines, errors)
    return errors


def main() -> int:
    workflows = sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in WORKFLOW_DIR.glob(pattern)
        if path.is_file()
    )
    if not workflows:
        print("ERROR: no GitHub Actions workflows were found")
        return 1

    errors: list[str] = []
    for path in workflows:
        errors.extend(check_workflow(path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        "Workflow policy passed: read-only permissions, hardened shell, timeouts, "
        "no external actions, no secret/token references, no high-risk triggers, "
        "and no direct GitHub expression expansion inside run blocks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
