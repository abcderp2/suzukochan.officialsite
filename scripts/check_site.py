#!/usr/bin/env python3
"""Read-only checks for the static site and its maintenance contract."""

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
SELF = Path(__file__).resolve()
OFFICIAL_URL = "https://abcderp2.github.io/suzukochan.officialsite/"
REPOSITORY_URL = "https://github.com/abcderp2/suzukochan.officialsite"
PROJECT_PATH = "/suzukochan.officialsite/"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
WARN_IMAGE_BYTES = 1 * 1024 * 1024

REQUIRED_MAINTENANCE_FILES = {
    "MAINTENANCE.md",
    "CHANGELOG.md",
}

OBSOLETE_MAINTENANCE_FILES = {
    "AI_HANDOFF.md",
    "FACTS.md",
    "PUBLISH_CHECKLIST.md",
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
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z0-9_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")),
    ("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
)


class SiteParser(html.parser.HTMLParser):
    """Collect the small set of HTML facts needed by the checks."""

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
    """Store all findings so one run gives a complete result."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
        path = path[len(PROJECT_PATH) :]
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
        reporter.error(f"{relative(current)}: forbidden URL scheme in {tag}: {value}")
        return

    for candidate in value.split(","):
        token = candidate.strip().split()[0] if candidate.strip() else ""
        if tag in {"img", "source"} and is_external(token):
            reporter.error(f"{relative(current)}: external image is not allowed: {token}")
            continue

        local = local_reference(token)
        if local is None:
            continue
        if local.as_posix() == "__outside_project__":
            reporter.error(f"{relative(current)}: root path outside project: {token}")
            continue

        resolved = (current.parent / local).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            reporter.error(f"{relative(current)}: reference escapes repository: {token}")
            continue
        if not resolved.exists():
            reporter.error(f"{relative(current)}: missing local file: {relative(resolved)}")


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
    name = relative(path)
    csp_values = [
        meta.get("content", "")
        for meta in parser.metas
        if meta.get("http-equiv", "").lower() == "content-security-policy"
    ]
    if len(csp_values) != 1:
        reporter.error(f"{name}: exactly one Content-Security-Policy meta is required")
        return

    try:
        policy = parse_csp(csp_values[0])
    except ValueError as error:
        reporter.error(f"{name}: invalid Content-Security-Policy: {error}")
        return

    for directive, expected in REQUIRED_CSP.items():
        if policy.get(directive) != expected:
            reporter.error(f"{name}: CSP {directive} must be {' '.join(sorted(expected))}")

    expected_scripts = {script_hash(block) for block in parser.json_ld} or {"'none'"}
    if policy.get("script-src") != expected_scripts:
        reporter.error(f"{name}: CSP script-src must match JSON-LD hash or be 'none'")

    if "upgrade-insecure-requests" not in policy:
        reporter.error(f"{name}: CSP upgrade-insecure-requests is required")

    for directive, tokens in policy.items():
        forbidden = tokens & FORBIDDEN_CSP_TOKENS
        if forbidden:
            reporter.error(
                f"{name}: CSP {directive} contains forbidden token(s): {' '.join(sorted(forbidden))}"
            )

    lowered = text.lower()
    csp_position = lowered.find('http-equiv="content-security-policy"')
    resource_positions = [
        position
        for position in (lowered.find("<link"), lowered.find("<script"))
        if position >= 0
    ]
    if resource_positions and csp_position > min(resource_positions):
        reporter.error(f"{name}: CSP meta must appear before resource-loading elements")


def check_html(path: Path, reporter: Reporter) -> None:
    parser = SiteParser()
    text = path.read_text(encoding="utf-8")
    parser.feed(text)
    name = relative(path)

    seen: set[str] = set()
    for element_id in parser.ids:
        if element_id in seen:
            reporter.error(f"{name}: duplicate id: {element_id}")
        seen.add(element_id)

    for tag in parser.forbidden_tags:
        reporter.error(f"{name}: forbidden HTML element: {tag}")
    for tag, attribute in parser.event_handlers:
        reporter.error(f"{name}: inline event handler is not allowed: {tag}[{attribute}]")
    for tag in parser.inline_styles:
        reporter.error(f"{name}: inline style is not allowed: {tag}")

    for image in parser.images:
        if "alt" not in image:
            reporter.error(f"{name}: img is missing alt: {image.get('src', '')}")

    for target in parser.target_blanks:
        rel_tokens = set(target.get("rel", "").lower().split())
        for required in ("noopener", "noreferrer"):
            if required not in rel_tokens:
                reporter.error(f"{name}: target=_blank without rel={required}")

    for tag, value in parser.references:
        check_reference(path, tag, value, reporter)

    for script in parser.scripts:
        src = script.get("src", "")
        script_type = script.get("type", "").lower()
        if src:
            reporter.error(f"{name}: executable script files are not allowed: {src}")
        elif script_type not in ALLOWED_INLINE_SCRIPT_TYPES:
            reporter.error(f"{name}: inline executable script is not allowed")

    for link in parser.links:
        rel_tokens = set(link.get("rel", "").lower().split())
        href = link.get("href", "")
        if "stylesheet" in rel_tokens and is_external(href):
            reporter.error(f"{name}: external stylesheet is not allowed: {href}")

    for block in parser.json_ld:
        try:
            json.loads(block)
        except json.JSONDecodeError as error:
            reporter.error(f"{name}: invalid JSON-LD: {error.msg}")

    meta_names = {
        meta.get("name", "").lower(): meta.get("content", "")
        for meta in parser.metas
    }
    if meta_names.get("referrer", "").lower() != "no-referrer":
        reporter.error(f"{name}: referrer policy must be no-referrer")
    for meta in parser.metas:
        if meta.get("http-equiv", "").lower() == "refresh":
            reporter.error(f"{name}: meta refresh is not allowed")

    check_csp(path, parser, text, reporter)

    if path.name == "index.html":
        meta_props = {
            meta.get("property", "").lower(): meta.get("content", "")
            for meta in parser.metas
        }
        if not meta_names.get("viewport") or not meta_names.get("description"):
            reporter.error("index.html: required meta is missing")
        for property_name in (
            "og:title",
            "og:type",
            "og:url",
            "og:image",
            "og:description",
            "og:site_name",
        ):
            if not meta_props.get(property_name):
                reporter.error(f"index.html: required meta property={property_name} is missing")
        canonical = next(
            (
                link.get("href", "")
                for link in parser.links
                if "canonical" in set(link.get("rel", "").split())
            ),
            "",
        )
        if canonical != OFFICIAL_URL:
            reporter.error(f"index.html: canonical must be {OFFICIAL_URL}")
        if meta_props.get("og:url") != OFFICIAL_URL:
            reporter.error(f"index.html: og:url must be {OFFICIAL_URL}")

    for url in re.findall(r"https?://[^\s\"'<>]+", text):
        if url.startswith("http://"):
            reporter.error(f"{name}: insecure http URL: {url}")
        if "abcderp2.github.io" in url and not url.startswith(OFFICIAL_URL):
            reporter.error(f"{name}: official URL typo: {url}")


def image_metadata_findings(path: Path) -> list[str]:
    data = path.read_bytes()
    findings: list[str] = []

    if data.startswith(b"\xff\xd8\xff"):
        offset = 2
        while offset + 3 < len(data):
            if data[offset] != 0xFF:
                break
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA:
                break
            if offset + 2 > len(data):
                break
            segment_length = int.from_bytes(data[offset:offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                break
            if marker == 0xFE or 0xE1 <= marker <= 0xEF:
                findings.append(f"JPEG marker 0x{marker:02X}")
            offset += segment_length
        return findings

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset:offset + 4], "big")
            chunk = data[offset + 4:offset + 8]
            end = offset + 12 + length
            if end > len(data):
                break
            if chunk in {b"eXIf", b"iTXt", b"tEXt", b"zTXt", b"iCCP"}:
                findings.append(f"PNG chunk {chunk.decode('ascii')}")
            offset = end
            if chunk == b"IEND":
                break
        return findings

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        offset = 12
        while offset + 8 <= len(data):
            chunk = data[offset:offset + 4]
            size = int.from_bytes(data[offset + 4:offset + 8], "little")
            end = offset + 8 + size + (size & 1)
            if end > len(data):
                break
            if chunk in {b"EXIF", b"XMP ", b"ICCP"}:
                findings.append(f"WebP chunk {chunk.decode('ascii', errors='replace')}")
            if chunk == b"VP8X" and size:
                flags = data[offset + 8]
                if flags & 0x20:
                    findings.append("WebP ICCP flag")
                if flags & 0x08:
                    findings.append("WebP EXIF flag")
                if flags & 0x04:
                    findings.append("WebP XMP flag")
            offset = end
        return findings

    return findings



def check_images(reporter: Reporter) -> None:
    directory = ROOT / "assets" / "images"
    if not directory.exists():
        reporter.error("assets/images directory is missing")
        return

    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        expected = expected_image_format(path)
        actual = image_signature(path)
        if expected and actual != expected:
            reporter.error(
                f"{relative(path)}: file extension expects {expected}, but bytes are {actual}"
            )
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            reporter.error(f"{relative(path)}: image is larger than 5 MiB")
        elif size > WARN_IMAGE_BYTES:
            reporter.warning(f"{relative(path)}: image is larger than 1 MiB")
        for finding in image_metadata_findings(path):
            reporter.error(
                f"{relative(path)}: image metadata is present ({finding}); use the separate Exif cleaner before upload"
            )


def check_css(reporter: Reporter) -> None:
    for path in ROOT.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"@import\s", text, flags=re.IGNORECASE):
            reporter.error(f"{relative(path)}: CSS @import is not allowed")
        for url in re.findall(
            r"url\(\s*['\"]?([^'\"\s)]+)",
            text,
            flags=re.IGNORECASE,
        ):
            if url.startswith(("data:", "http://", "https://")) or is_external(url):
                reporter.error(
                    f"{relative(path)}: external, data, or insecure CSS URL: {url}"
                )


def check_secrets(reporter: Reporter) -> None:
    suffixes = {
        ".conf",
        ".css",
        ".env",
        ".html",
        ".ini",
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
    ignored_parts = {".git", ".venv", "__pycache__"}

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == SELF or ignored_parts & set(path.parts):
            continue
        if path.suffix.lower() not in suffixes and path.name != ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            reporter.error(f"{relative(path)}: expected text file is not valid UTF-8")
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                reporter.error(f"{relative(path)}: possible {label}")


def check_workflows(reporter: Reporter) -> None:
    directory = ROOT / ".github" / "workflows"
    if not directory.exists():
        reporter.error(".github/workflows directory is missing")
        return

    workflows = sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml")))
    if not workflows:
        reporter.error(".github/workflows: no workflow file found")
        return

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        required_snippets = (
            "permissions:\n  contents: read",
            "timeout-minutes:",
            "shell: bash --noprofile --norc -euo pipefail {0}",
            "python3 -I scripts/check_site.py",
        )
        for snippet in required_snippets:
            if snippet not in text:
                reporter.error(
                    f"{relative(path)}: missing workflow hardening setting: {snippet.splitlines()[0]}"
                )

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
                reporter.error(f"{relative(path)}: forbidden {label}")


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
            reporter.error(f"{relative(path)}: symbolic links are not allowed")
        if path.is_file() and path.name in {".env", "id_ed25519", "id_rsa"}:
            reporter.error(f"{relative(path)}: sensitive file must not be committed")


def check_maintenance_contract(reporter: Reporter) -> None:
    for filename in sorted(REQUIRED_MAINTENANCE_FILES):
        if not (ROOT / filename).is_file():
            reporter.error(f"{filename}: required maintenance file is missing")

    for filename in sorted(OBSOLETE_MAINTENANCE_FILES):
        if (ROOT / filename).exists():
            reporter.error(
                f"{filename}: obsolete maintenance instructions must remain consolidated in MAINTENANCE.md"
            )

    readme = ROOT / "README.md"
    if not readme.is_file():
        reporter.error("README.md is missing")
    elif "MAINTENANCE.md" not in readme.read_text(encoding="utf-8"):
        reporter.error("README.md: link or reference to MAINTENANCE.md is required")

    manual = ROOT / "MAINTENANCE.md"
    if manual.is_file():
        text = manual.read_text(encoding="utf-8")
        required_facts = (
            OFFICIAL_URL,
            REPOSITORY_URL,
            "python3 -I scripts/check_site.py",
            "Squash and merge",
            "Revert",
        )
        for fact in required_facts:
            if fact not in text:
                reporter.error(f"MAINTENANCE.md: required fact is missing: {fact}")



class BilingualParser(html.parser.HTMLParser):
    """Collect the language and cross-page facts for the bilingual pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.title_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.anchors: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.sections: list[str] = []
        self.images: list[dict[str, str]] = []
        self.sources: list[dict[str, str]] = []
        self.news_items: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []
        self._section_id: str | None = None
        self._news_item: dict[str, str] | None = None
        self._news_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "link":
            self.links.append(values)
        elif tag == "a":
            self.anchors.append(values)
        elif tag == "meta":
            self.metas.append(values)
        elif tag == "img":
            self.images.append(values)
        elif tag == "source":
            self.sources.append(values)
        elif tag == "section":
            self.sections.append(values.get("id", ""))
            self._section_id = values.get("id", "")
        elif tag == "li" and self._section_id == "news":
            self._news_item = {"datetime": ""}
            self._news_text = []
        elif tag == "time" and self._news_item is not None:
            self._news_item["datetime"] = values.get("datetime", "")
        elif tag == "script":
            if values.get("type", "").lower() == "application/ld+json":
                self._in_json_ld = True
                self._json_ld_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)
        if self._news_item is not None:
            self._news_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._json_ld_parts))
            self._in_json_ld = False
            self._json_ld_parts = []
        elif tag == "li" and self._news_item is not None:
            self._news_item["text"] = " ".join("".join(self._news_text).split())
            self.news_items.append(self._news_item)
            self._news_item = None
            self._news_text = []
        elif tag == "section":
            self._section_id = None


def bilingual_meta(parser: BilingualParser, key: str, attribute: str) -> str:
    for meta in parser.metas:
        if meta.get(attribute, "").lower() == key.lower():
            return meta.get("content", "")
    return ""


def bilingual_link_hrefs(parser: BilingualParser, rel: str) -> list[str]:
    return [
        link.get("href", "")
        for link in parser.links
        if rel in {token.lower() for token in link.get("rel", "").split()}
    ]


def bilingual_image_sources(parser: BilingualParser) -> list[str]:
    values: list[str] = []
    for image in parser.images:
        if image.get("src"):
            values.append(image["src"])
    for source in parser.sources:
        if source.get("srcset"):
            values.extend(
                candidate.strip().split()[0]
                for candidate in source["srcset"].split(",")
                if candidate.strip()
            )
    return values


def bilingual_external_anchors(parser: BilingualParser) -> set[str]:
    return {
        anchor.get("href", "")
        for anchor in parser.anchors
        if is_external(anchor.get("href", ""))
        and anchor.get("href", "") not in {OFFICIAL_URL, OFFICIAL_URL + "en.html"}
    }


def check_bilingual_page(
    path: Path,
    expected_lang: str,
    expected_switch_href: str,
    expected_switch_label: str,
    expected_switch_lang: str,
    expected_news_text: str,
    reporter: Reporter,
) -> BilingualParser:
    if not path.is_file():
        reporter.error(f"{path.relative_to(ROOT)}: bilingual page is missing")
        return BilingualParser()

    parser = BilingualParser()
    text = path.read_text(encoding="utf-8")
    parser.feed(text)
    name = path.relative_to(ROOT).as_posix()
    expected_url = OFFICIAL_URL if expected_lang == "ja" else OFFICIAL_URL + "en.html"

    if parser.html_lang != expected_lang:
        reporter.error(f"{name}: html lang must be {expected_lang}")

    switches = [
        anchor
        for anchor in parser.anchors
        if "language-switch" in anchor.get("class", "").split()
    ]
    if len(switches) != 1:
        reporter.error(f"{name}: exactly one language-switch link is required")
    else:
        switch = switches[0]
        if switch.get("href") != expected_switch_href:
            reporter.error(f"{name}: language-switch href is incorrect")
        if switch.get("hreflang") != expected_switch_lang:
            reporter.error(f"{name}: language-switch hreflang is incorrect")
        if switch.get("target"):
            reporter.error(f"{name}: language-switch must be a normal link")
        if expected_switch_label not in switch.get("class", "") + text:
            reporter.error(f"{name}: language-switch label is missing")

    canonical = bilingual_link_hrefs(parser, "canonical")
    if canonical != [expected_url]:
        reporter.error(f"{name}: canonical must be {expected_url}")

    expected_alternates = {
        "ja": OFFICIAL_URL,
        "en": OFFICIAL_URL + "en.html",
        "x-default": OFFICIAL_URL,
    }
    actual_alternates = {
        link.get("hreflang", ""): link.get("href", "")
        for link in parser.links
        if "alternate" in {token.lower() for token in link.get("rel", "").split()}
    }
    if actual_alternates != expected_alternates:
        reporter.error(f"{name}: alternate hreflang links are incorrect")

    expected_sections = ["gallery", "profile", "about", "news", "guidelines", "sns"]
    if parser.sections != expected_sections:
        reporter.error(f"{name}: section ids or order are incorrect")

    if not parser.news_items:
        reporter.error(f"{name}: update history is missing")
    else:
        latest = parser.news_items[0]
        if latest.get("datetime") != "2026-07-18" or expected_news_text not in latest.get("text", ""):
            reporter.error(f"{name}: latest update history is incorrect")

    if BILINGUAL_TRANSLATION_MARKERS.search(text):
        reporter.error(f"{name}: external translation service reference is not allowed")

    if expected_lang == "en":
        if "".join(parser.title_parts).strip() != "Suzuko-chan Official Site":
            reporter.error("en.html: title is not English")
        expected_meta = {
            "description": "The official site of Suzuko-chan, featuring her profile, updates, and guidelines.",
            "og:title": "Suzuko-chan Official Site",
            "og:url": OFFICIAL_URL + "en.html",
            "og:description": "The official site of Suzuko-chan, featuring her profile, updates, and guidelines.",
            "og:site_name": "Suzuko-chan Official Site",
            "twitter:title": "Suzuko-chan Official Site",
            "twitter:description": "The official site of Suzuko-chan, featuring her profile, updates, and guidelines.",
        }
        for key, value in expected_meta.items():
            attribute = "property" if key.startswith("og:") else "name"
            if bilingual_meta(parser, key, attribute) != value:
                reporter.error(f"en.html: {key} metadata is not English or has the wrong URL")
        if not parser.json_ld:
            reporter.error("en.html: English JSON-LD is missing")
        else:
            try:
                data = json.loads(parser.json_ld[0])
            except json.JSONDecodeError as error:
                reporter.error(f"en.html: invalid JSON-LD: {error.msg}")
            else:
                if data.get("url") != OFFICIAL_URL + "en.html":
                    reporter.error("en.html: JSON-LD URL must be the English URL")
                if re.search(r"[ぁ-んァ-ン一-龯]", data.get("description", "")):
                    reporter.error("en.html: JSON-LD description must be English")

    return parser


def check_bilingual_pages(reporter: Reporter) -> None:
    translation_markers = (
        r"translate\.google",
        r"translate\.goog",
        r"deepl\.com",
        r"libretranslate",
        r"gtranslate",
        r"translation\.googleapis",
    )
    global BILINGUAL_TRANSLATION_MARKERS
    BILINGUAL_TRANSLATION_MARKERS = re.compile(
        "|".join(translation_markers),
        flags=re.IGNORECASE,
    )

    ja = check_bilingual_page(
        ROOT / "index.html",
        "ja",
        "en.html",
        "English",
        "en",
        "英語版と日本語・英語切り替え機能を追加",
        reporter,
    )
    en = check_bilingual_page(
        ROOT / "en.html",
        "en",
        "index.html",
        "日本語",
        "ja",
        "Added an English version and Japanese–English language switching",
        reporter,
    )

    if bilingual_image_sources(ja) != bilingual_image_sources(en):
        reporter.error("index.html and en.html: image references do not match")
    ja_css = bilingual_link_hrefs(ja, "stylesheet")
    en_css = bilingual_link_hrefs(en, "stylesheet")
    if ja_css != en_css:
        reporter.error("index.html and en.html: stylesheet references do not match")
    if bilingual_external_anchors(ja) != bilingual_external_anchors(en):
        reporter.error("index.html and en.html: external links do not match")


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
    check_maintenance_contract(reporter)
    check_bilingual_pages(reporter)

    print("Static site and maintenance check")
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
