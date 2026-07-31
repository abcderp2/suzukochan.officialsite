#!/usr/bin/env python3
"""Read-only secret and repository security audit for the static site."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_FINDINGS = 100

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "OpenAI API key",
        re.compile(r"\bsk-(?:(?:proj|svcacct)-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    (
        "GitHub fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")),
    (
        "Stripe live key",
        re.compile(r"\b(?:sk|rk|pk)_live_[A-Za-z0-9]{16,}\b"),
    ),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
)

CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?im)\b(?:"
    r"OPENAI_API_KEY|OPENAI_KEY|API_KEY|ACCESS_TOKEN|AUTH_TOKEN|"
    r"CLIENT_SECRET|GITHUB_TOKEN|PRIVATE_KEY|SECRET_KEY|PASSWORD"
    r")\b\s*[:=]\s*[\"']?([A-Za-z0-9_./+=:-]{16,})"
)

PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "replace_me",
    "replace-me",
    "your_",
    "your-",
    "dummy",
    "sample",
    "test_only",
    "test-only",
    "changeme",
)

SENSITIVE_EXACT_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
}
SENSITIVE_SUFFIXES = {".jks", ".key", ".p12", ".pem", ".pfx"}
ALLOWED_EXAMPLE_NAMES = {".env.example", ".env.sample"}


class Findings:
    """Collect sanitized findings without printing secret values."""

    def __init__(self) -> None:
        self._items: list[str] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, category: str, location: str, value: str = "") -> None:
        fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else ""
        key = (category, fingerprint or location)
        if key in self._seen or len(self._items) >= MAX_FINDINGS:
            return
        self._seen.add(key)
        suffix = f"; fingerprint={fingerprint}" if fingerprint else ""
        self._items.append(f"{category}: {location}{suffix}")

    @property
    def items(self) -> list[str]:
        return self._items


def git_bytes(*args: str, input_data: bytes | None = None) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    if len(set(value)) <= 4:
        return True
    return False


def scan_text(label: str, text: str, findings: Findings) -> None:
    for category, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            location = f"{label}:{line_number(text, match.start())}"
            findings.add(category, location, match.group(0))

    for match in CREDENTIAL_ASSIGNMENT.finditer(text):
        value = match.group(1)
        if looks_like_placeholder(value):
            continue
        location = f"{label}:{line_number(text, match.start())}"
        findings.add("credential-like assignment", location, value)


def sensitive_path(path_text: str) -> bool:
    path = Path(path_text)
    name = path.name.lower()
    if name in ALLOWED_EXAMPLE_NAMES:
        return False
    if name in SENSITIVE_EXACT_NAMES:
        return True
    if name.startswith(".env."):
        return True
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if name.startswith("credentials.") and name.endswith(".json"):
        return True
    if name.startswith("service-account") and name.endswith(".json"):
        return True
    return False


def decode_text(data: bytes) -> str | None:
    if len(data) > MAX_TEXT_BYTES or b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def tracked_paths() -> list[str]:
    output = git_bytes("ls-files", "-z")
    return [part.decode("utf-8", errors="surrogateescape") for part in output.split(b"\x00") if part]


def scan_current(findings: Findings) -> None:
    for path_text in tracked_paths():
        if sensitive_path(path_text):
            findings.add("sensitive filename committed", path_text)

        path = ROOT / path_text
        try:
            data = path.read_bytes()
        except OSError as error:
            findings.add("unreadable tracked file", f"{path_text}: {error}")
            continue
        text = decode_text(data)
        if text is not None:
            scan_text(f"current:{path_text}", text, findings)


def batch_object_metadata(object_ids: list[str]) -> dict[str, tuple[str, int]]:
    if not object_ids:
        return {}
    query = "".join(f"{object_id}\n" for object_id in object_ids).encode("ascii")
    output = git_bytes(
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_data=query,
    )
    metadata: dict[str, tuple[str, int]] = {}
    for line in output.decode("ascii", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].isdigit():
            metadata[parts[0]] = (parts[1], int(parts[2]))
    return metadata


def batch_blobs(object_ids: list[str]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    query = "".join(f"{object_id}\n" for object_id in object_ids).encode("ascii")
    output = git_bytes("cat-file", "--batch", input_data=query)
    blobs: dict[str, bytes] = {}
    cursor = 0
    for requested in object_ids:
        newline = output.find(b"\n", cursor)
        if newline < 0:
            raise RuntimeError("git cat-file returned an incomplete header")
        header = output[cursor:newline].decode("ascii", errors="replace")
        cursor = newline + 1
        parts = header.split()
        if len(parts) != 3 or not parts[2].isdigit():
            raise RuntimeError(f"unexpected git cat-file header for {requested}: {header}")
        object_id, object_type, size_text = parts
        size = int(size_text)
        data = output[cursor:cursor + size]
        cursor += size
        if cursor >= len(output) or output[cursor:cursor + 1] != b"\n":
            raise RuntimeError(f"git cat-file returned incomplete data for {requested}")
        cursor += 1
        if object_type == "blob":
            blobs[object_id] = data
    return blobs


def history_objects() -> tuple[dict[str, set[str]], list[str]]:
    paths_by_object: dict[str, set[str]] = defaultdict(set)
    object_order: list[str] = []
    seen: set[str] = set()
    for raw_line in git_bytes("rev-list", "--objects", "--all").splitlines():
        object_id_bytes, separator, path_bytes = raw_line.partition(b" ")
        object_id = object_id_bytes.decode("ascii")
        if object_id not in seen:
            object_order.append(object_id)
            seen.add(object_id)
        if separator:
            paths_by_object[object_id].add(path_bytes.decode("utf-8", errors="replace"))
    return paths_by_object, object_order


def scan_history(findings: Findings) -> None:
    paths_by_object, object_order = history_objects()
    metadata = batch_object_metadata(object_order)
    blob_ids = [
        object_id
        for object_id in object_order
        if metadata.get(object_id, ("", 0))[0] == "blob"
        and metadata.get(object_id, ("", 0))[1] <= MAX_TEXT_BYTES
    ]

    for start in range(0, len(blob_ids), 200):
        for object_id, data in batch_blobs(blob_ids[start:start + 200]).items():
            paths = sorted(paths_by_object.get(object_id) or {"unknown-path"})
            for path_text in paths:
                if sensitive_path(path_text):
                    findings.add(
                        "sensitive filename in Git history",
                        f"history:{object_id[:12]}:{path_text}",
                    )
            text = decode_text(data)
            if text is None:
                continue
            label = f"history:{object_id[:12]}:{paths[0]}"
            scan_text(label, text, findings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        action="store_true",
        help="scan every reachable Git blob in all fetched refs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = Findings()

    try:
        scan_current(findings)
        if args.history:
            scan_history(findings)
    except RuntimeError as error:
        print(f"ERROR: security audit could not complete: {error}")
        return 2

    if findings.items:
        for item in findings.items:
            print(f"ERROR: {item}")
        if len(findings.items) >= MAX_FINDINGS:
            print(f"ERROR: finding output stopped at {MAX_FINDINGS} items")
        print(
            "Security audit failed. Revoke exposed credentials before removing "
            "them from Git history."
        )
        return 1

    scope = "current tree and Git history" if args.history else "current tree"
    print(
        "Security audit passed: no known credential pattern was found in the "
        f"{scope}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
