#!/usr/bin/env python3
"""Read-only checks for the static GitHub Pages site."""

from __future__ import annotations

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

KNOWN_IMAGE_ISSUES = {
    "assets/images/suzuko-gallery.jpg",
    "assets/images/suzuko-gallery.webp",
    "assets/images/suzuko-gallery2.jpg",
    "assets/images/suzuko-gallery2.webp",
}

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
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
        self._json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
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
        if tag == "script" and self._json_ld:
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

    def image_issue(self, path: Path, message: str) -> None:
        relative = path.relative_to(ROOT).as_posix()
        if relative in KNOWN_IMAGE_ISSUES:
            self.warning(f"KNOWN IMAGE ISSUE: {relative}: {message}")
        else:
            self.error(f"{relative}: {message}")


def is_external(value: str) -> bool:
    parts = urlsplit(value)
    return bool(parts.scheme or parts.netloc)


def local_reference(value: str) -> Path | None:
    value = value.strip()
    if not value or value.startswith(("#", "data:", "mailto:", "tel:", "javascript:")):
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


def check_reference(current: Path, value: str, reporter: Reporter) -> None:
    for candidate in value.split(","):
        token = candidate.strip().split()[0] if candidate.strip() else ""
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

    for image in parser.images:
        if "alt" not in image:
            reporter.error(f"{relative}: img is missing alt: {image.get('src', '')}")

    for target in parser.target_blanks:
        if "noopener" not in set(target.get("rel", "").lower().split()):
            reporter.error(f"{relative}: target=_blank without rel=noopener")

    for _, value in parser.references:
        check_reference(path, value, reporter)

    for script in parser.scripts:
        src = script.get("src", "")
        if src and is_external(src):
            reporter.error(f"{relative}: external JavaScript is not allowed: {src}")

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

    if path.name == "index.html":
        meta_names = {m.get("name", "").lower(): m.get("content", "") for m in parser.metas}
        meta_props = {m.get("property", "").lower(): m.get("content", "") for m in parser.metas}
        if not meta_names.get("viewport") or not meta_names.get("description"):
            reporter.error("index.html: required meta is missing")
        for name in ("og:title", "og:type", "og:url", "og:image", "og:description", "og:site_name"):
            if not meta_props.get(name):
                reporter.error(f"index.html: required meta property={name} is missing")
        canonical = next((l.get("href", "") for l in parser.links if "canonical" in set(l.get("rel", "").split())), "")
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
            reporter.image_issue(path, f"file extension expects {expected}, but bytes are {actual}")
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            reporter.error(f"{path.relative_to(ROOT)}: image is larger than 5 MiB")
        elif size > WARN_IMAGE_BYTES:
            reporter.warning(f"{path.relative_to(ROOT)}: image is larger than 1 MiB")


def check_css(reporter: Reporter) -> None:
    for path in ROOT.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        for url in re.findall(r"url\(\s*['\"]?([^'\"\s)]+)", text, flags=re.IGNORECASE):
            if url.startswith("http://") or is_external(url):
                reporter.error(f"{path.relative_to(ROOT)}: external or insecure CSS URL: {url}")


def check_secrets(reporter: Reporter) -> None:
    suffixes = {".html", ".css", ".md", ".txt", ".yml", ".yaml", ".py", ".xml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                reporter.error(f"{path.relative_to(ROOT)}: possible {label}")


def main() -> int:
    reporter = Reporter()
    for path in sorted(ROOT.rglob("*.html")):
        check_html(path, reporter)
    check_images(reporter)
    check_css(reporter)
    check_secrets(reporter)

    print("Static site check")
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
