#!/usr/bin/env python3
"""Read-only security and integrity checks for the static GitHub Pages site."""

from __future__ import annotations

import base64
import hashlib
import html.parser
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_URL = "https://abcderp2.github.io/suzukochan.officialsite/"
PROJECT_PATH = "/suzukochan.officialsite/"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
WARN_IMAGE_BYTES = 1 * 1024 * 1024

KNOWN_MISSING_REFERENCES = {
    "favicon.ico",
    "assets/images/apple-touch-icon.png",
}

FORBIDDEN_HTML_TAGS = {"base", "embed", "form", "iframe", "object"}
ALLOWED_INLINE_SCRIPT_TYPES = {"application/ld+json"}

REQUIRED_CSP = {
    "default-src": {"'none'"},
    "base-uri": {"'none'"},
    "connect-src": {"'none'"},
    "form-action": {"'none'"},
    "frame-src": {"'none'"},
    "img-src": {"'self'"},
    "manifest-src": {"'none'"},
    "media-src": {"'none'"},
    "object-src": {"'none'"},
    "style-src": {"'self'"},
    "worker-src": {"'none'"},
}

FORBIDDEN_CSP_TOKENS = {
    "*",
    "'unsafe-eval'",
    "'unsafe-inline'",
    "blob:",
    "data:",
    "http:",
    "https:",
}

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("PGP private key", re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")),
    ("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
)


class SiteParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.images: list[dict[str, str]] = []
        self.references: list[tuple[str, str]] = []
        self.target_blanks: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self.event_handlers: list[tuple[str, str]] = []
        self.inline_styles: list[str] = []
        self.forbidden_tags: list[str] = []
        self._json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}

        if tag in FORBIDDEN_HTML_TAGS:
            self.forbidden_tags.append(tag)
        for name in values:
            if name.startswith("on"):
                self.event_handlers.append((tag, name))
        if "style" in values or tag == "style":
            self.inline_styles.append(tag)

        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "img":
            self.images.append(values)
        if tag in {"a", "area", "link", "script", "img", "source"}:
            for name in ("href", "src", "srcset"):
                if values.get(name):
                    self.references.append((tag, values[name]))
        if tag in {"a", "area"} and values.get("target", "").lower() == "_blank":
            self.target_blanks.append(values)
        if tag == "meta":
            self.metas.append(values)
        if tag == "link":
            self.links.append(values)
        if tag == "script":
            self.scripts.append(values)
            if values.get("type", "").lower() == "application/ld+json":
                self._json_ld = True
                self._json_ld_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._json_ld:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._json_ld:
            self.json_ld.append("".join(self._json_ld_parts))
            self._json_ld = False
            self._json_ld_parts = []


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def is_external(value: str) -> bool:
    parts = urlsplit(value)
    return bool(parts.scheme or parts.netloc)


def local_reference(value: str) -> Path | None:
    value = value.strip()
    if not value or value.startswith(("#", "mailto:", "tel:")):
        return None
    if is_external(value):
        return None
    path = unquote(urlsplit(value).path)
    if path in {PROJECT_PATH, PROJECT_PATH.rstrip("/")}:
        return Path("index.html")
    if path.startswith(PROJECT_PATH):
        path = path[len(PROJECT_PATH):]
    elif path.startswith("/"):
        return Path("__outside_project__")
    return Path(path)


def image_signature(path: Path) -> str:
    data = path.read_bytes()[:16]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif"
    return "unknown"


def expected_image_format(path: Path) -> str | None:
    return {
        ".png": "png",
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".webp": "webp",
        ".gif": "gif",
    }.get(path.suffix.lower())


def check_reference(current: Path, tag: str, value: str, reporter: Reporter) -> None:
    lowered = value.strip().lower()
    if lowered.startswith(("data:", "javascript:", "vbscript:")):
        reporter.error(f"{current.relative_to(ROOT)}: forbidden URL scheme in {tag}: {value}")
        return

    for candidate in value.split(","):
        token = candidate.strip().split()[0] if candidate.strip() else ""
        if tag in {"img", "source"} and is_external(token):
            reporter.error(f"{current.relative_to(ROOT)}: external image is not allowed: {token}")
            continue
        local = local_reference(token)
        if local is None:
            continue
        if local.as_posix() == "__outside_project__":
            reporter.error(f"{current.relative_to(ROOT)}: root path outside project: {token}")
            continue
        resolved = (current.parent / local).resolve()
        try:
            relative = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            reporter.error(f"{current.relative_to(ROOT)}: reference escapes repository: {token}")
            continue
        if not resolved.exists():
            if relative in KNOWN_MISSING_REFERENCES:
                reporter.warning(f"KNOWN MISSING REFERENCE: {current.relative_to(ROOT)}: {relative}")
            else:
                reporter.error(f"{current.relative_to(ROOT)}: missing local file: {relative}")


def parse_csp(content: str) -> dict[str, set[str]]:
    policy: dict[str, set[str]] = {}
    for raw_directive in content.split(";"):
        parts = raw_directive.strip().split()
        if not parts:
            continue
        name = parts[0].lower()
        if name in policy:
            raise ValueError(f"duplicate directive: {name}")
        policy[name] = set(parts[1:])
    return policy


def script_hash(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"


def check_csp(path: Path, parser: SiteParser, text: str, reporter: Reporter) -> None:
    relative = path.relative_to(ROOT).as_posix()
    csp_values = [
        meta.get("content", "")
        for meta in parser.metas
        if meta.get("http-equiv", "").lower() == "content-security-policy"
    ]
    if len(csp_values) != 1:
        reporter.error(f"{relative}: exactly one Content-Security-Policy meta is required")
        return

    try:
        policy = parse_csp(csp_values[0])
    except ValueError as error:
        reporter.error(f"{relative}: invalid Content-Security-Policy: {error}")
        return

    for directive, expected in REQUIRED_CSP.items():
        if policy.get(directive) != expected:
            reporter.error(f"{relative}: CSP {directive} must be {' '.join(sorted(expected))}")

    expected_scripts = {script_hash(block) for block in parser.json_ld} or {"'none'"}
    if policy.get("script-src") != expected_scripts:
        reporter.error(
            f"{relative}: CSP script-src must match the inline JSON-LD hash or be 'none'"
        )

    if "upgrade-insecure-requests" not in policy:
        reporter.error(f"{relative}: CSP upgrade-insecure-requests is required")
    if "frame-ancestors" in policy:
        reporter.warning(f"{relative}: frame-ancestors is ignored in a meta CSP")

    for directive, tokens in policy.items():
        forbidden = tokens & FORBIDDEN_CSP_TOKENS
        if forbidden:
            reporter.error(
                f"{relative}: CSP {directive} contains forbidden token(s): {' '.join(sorted(forbidden))}"
            )

    csp_position = text.lower().find('http-equiv="content-security-policy"')
    first_resource = min(
        (position for position in (text.lower().find("<link"), text.lower().find("<script")) if position >= 0),
        default=-1,
    )
    if first_resource >= 0 and csp_position > first_resource:
        reporter.error(f"{relative}: CSP meta must appear before resource-loading elements")


def check_html(path: Path, reporter: Reporter) -> None:
    parser = SiteParser()
    text = path.read_text(encoding="utf-8")
    parser.feed(text)
    relative = path.relative_to(ROOT).as_posix()

    seen: set[str] = set()
    for element_id in parser.ids:
        if element_id in seen:
            reporter.error(f"{relative}: duplicate id: {element_id}")
        seen.add(element_id)

    for tag in parser.forbidden_tags:
        reporter.error(f"{relative}: forbidden HTML element: {tag}")
    for tag, attribute in parser.event_handlers:
        reporter.error(f"{relative}: inline event handler is not allowed: {tag}[{attribute}]")
    for tag in parser.inline_styles:
        reporter.error(f"{relative}: inline style is not allowed: {tag}")

    for image in parser.images:
        if "alt" not in image:
            reporter.error(f"{relative}: img is missing alt: {image.get('src', '')}")

    for target in parser.target_blanks:
        rel_tokens = set(target.get("rel", "").lower().split())
        for required in ("noopener", "noreferrer"):
            if required not in rel_tokens:
                reporter.error(f"{relative}: target=_blank without rel={required}")

    for tag, value in parser.references:
        check_reference(path, tag, value, reporter)

    for script in parser.scripts:
        src = script.get("src", "")
        script_type = script.get("type", "").lower()
        if src:
            if is_external(src):
                reporter.error(f"{relative}: external JavaScript is not allowed: {src}")
            else:
                reporter.error(f"{relative}: executable script files are not allowed: {src}")
        elif script_type not in ALLOWED_INLINE_SCRIPT_TYPES:
            reporter.error(f"{relative}: inline executable script is not allowed")

    for link in parser.links:
        rel_tokens = set(link.get("rel", "").lower().split())
        href = link.get("href", "")
        if "stylesheet" in rel_tokens and is_external(href):
            reporter.error(f"{relative}: external stylesheet is not allowed: {href}")

    for block in parser.json_ld:
        try:
            json.loads(block)
        except json.JSONDecodeError as error:
            reporter.error(f"{relative}: invalid JSON-LD: {error.msg}")

    meta_names = {m.get("name", "").lower(): m.get("content", "") for m in parser.metas}
    if meta_names.get("referrer", "").lower() != "no-referrer":
        reporter.error(f"{relative}: referrer policy must be no-referrer")
    for meta in parser.metas:
        if meta.get("http-equiv", "").lower() == "refresh":
            reporter.error(f"{relative}: meta refresh is not allowed")

    check_csp(path, parser, text, reporter)

    if path.name == "index.html":
        meta_props = {m.get("property", "").lower(): m.get("content", "") for m in parser.metas}
        if not meta_names.get("viewport") or not meta_names.get("description"):
            reporter.error("index.html: required meta is missing")
        for name in ("og:title", "og:type", "og:url", "og:image", "og:description", "og:site_name"):
            if not meta_props.get(name):
                reporter.error(f"index.html: required meta property={name} is missing")
        canonical = next(
            (link.get("href", "") for link in parser.links if "canonical" in set(link.get("rel", "").split())),
            "",
        )
        if canonical != OFFICIAL_URL:
            reporter.error(f"index.html: canonical must be {OFFICIAL_URL}")
        if meta_props.get("og:url") != OFFICIAL_URL:
            reporter.error(f"index.html: og:url must be {OFFICIAL_URL}")

    for url in re.findall(r"https?://[^\s\"'<>]+", text):
        if url.startswith("http://"):
            reporter.error(f"{relative}: insecure http URL: {url}")
        if "abcderp2.github.io" in url and not url.startswith(OFFICIAL_URL):
            reporter.error(f"{relative}: official URL typo: {url}")


def check_images(reporter: Reporter) -> None:
    directory = ROOT / "assets" / "images"
    if not directory.exists():
        reporter.error("assets/images directory is missing")
        return
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        expected = expected_image_format(path)
        actual = image_signature(path)
        if expected and actual != expected:
            reporter.error(f"{path.relative_to(ROOT)}: file extension expects {expected}, but bytes are {actual}")
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            reporter.error(f"{path.relative_to(ROOT)}: image is larger than 5 MiB")
        elif size > WARN_IMAGE_BYTES:
            reporter.warning(f"{path.relative_to(ROOT)}: image is larger than 1 MiB")


def check_css(reporter: Reporter) -> None:
    for path in ROOT.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"@import\s", text, flags=re.IGNORECASE):
            reporter.error(f"{path.relative_to(ROOT)}: CSS @import is not allowed")
        for url in re.findall(r"url\(\s*['\"]?([^'\"\s)]+)", text, flags=re.IGNORECASE):
            if url.startswith(("data:", "http://", "https://")) or is_external(url):
                reporter.error(f"{path.relative_to(ROOT)}: external, data, or insecure CSS URL: {url}")


def check_secrets(reporter: Reporter) -> None:
    suffixes = {".conf", ".css", ".env", ".html", ".ini", ".json", ".md", ".py", ".toml", ".txt", ".xml", ".yaml", ".yml"}
    ignored_parts = {".git", ".venv", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ignored_parts & set(path.parts):
            continue
        if path.suffix.lower() not in suffixes and path.name != ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            reporter.error(f"{path.relative_to(ROOT)}: expected text file is not valid UTF-8")
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                reporter.error(f"{path.relative_to(ROOT)}: possible {label}")


def check_workflows(reporter: Reporter) -> None:
    directory = ROOT / ".github" / "workflows"
    if not directory.exists():
        reporter.error(".github/workflows directory is missing")
        return

    for path in sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        required_snippets = (
            "permissions:\n  contents: read",
            "timeout-minutes:",
            "shell: bash --noprofile --norc -euo pipefail {0}",
            "python3 -I scripts/check_site.py",
        )
        for snippet in required_snippets:
            if snippet not in text:
                reporter.error(f"{relative}: missing workflow hardening setting: {snippet.splitlines()[0]}")

        forbidden_patterns = (
            ("third-party or reusable action", r"(?m)^\s*uses:\s*"),
            ("pull_request_target trigger", r"(?m)^\s*pull_request_target\s*:"),
            ("workflow_run trigger", r"(?m)^\s*workflow_run\s*:"),
            ("write-all permission", r"(?m)^\s*permissions\s*:\s*write-all\s*$"),
            ("contents write permission", r"(?m)^\s*contents\s*:\s*write\s*$"),
            ("id-token write permission", r"(?m)^\s*id-token\s*:\s*write\s*$"),
            ("workflow secret access", r"\$\{\{\s*secrets\."),
        )
        for label, pattern in forbidden_patterns:
            if re.search(pattern, text):
                reporter.error(f"{relative}: forbidden {label}")


def check_gitignore(reporter: Reporter) -> None:
    path = ROOT / ".gitignore"
    if not path.exists():
        reporter.error(".gitignore is missing")
        return
    entries = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {
        ".env",
        ".env.*",
        "*.jks",
        "*.key",
        "*.p12",
        "*.pem",
        "*.pfx",
        "*.py[cod]",
        "__pycache__/",
        "id_ed25519*",
        "id_rsa*",
    }
    for entry in sorted(required - entries):
        reporter.error(f".gitignore: missing sensitive-file pattern: {entry}")


def check_repository_shape(reporter: Reporter) -> None:
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            reporter.error(f"{path.relative_to(ROOT)}: symbolic links are not allowed")
        if path.is_file() and path.name in {".env", "id_ed25519", "id_rsa"}:
            reporter.error(f"{path.relative_to(ROOT)}: sensitive file must not be committed")


def main() -> int:
    reporter = Reporter()
    for path in sorted(ROOT.rglob("*.html")):
        check_html(path, reporter)
    check_images(reporter)
    check_css(reporter)
    check_secrets(reporter)
    check_workflows(reporter)
    check_gitignore(reporter)
    check_repository_shape(reporter)

    print("Static site security check")
    for warning in reporter.warnings:
        print(f"WARNING: {warning}")
    for error in reporter.errors:
        print(f"ERROR: {error}")
    if reporter.errors:
        print(f"FAILED: {len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)")
        return 1
    print(f"PASSED: {len(reporter.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
