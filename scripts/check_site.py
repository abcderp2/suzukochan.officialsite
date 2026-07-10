#!/usr/bin/env python3
"""Read-only checks for the static site. No network access or file changes."""

from __future__ import annotations

import datetime as dt
import html.parser
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_URL = "https://abcderp2.github.io/suzukochan.officialsite/"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
WARN_IMAGE_BYTES = 1 * 1024 * 1024
ALLOWLIST_EXPIRY = dt.date(2026, 12, 31)

# These are deliberately visible temporary exceptions. The image bytes and
# references are protected from changes in this pull request. Remove each entry
# when the owner approves correcting that file.
KNOWN_IMAGE_ISSUES = {
    "assets/images/suzuko-gallery.jpg": (
        "PNG bytes use a .jpg name and index.html/OG metadata declare old dimensions."
    ),
    "assets/images/suzuko-gallery.webp": (
        "PNG bytes use a .webp name; it is the current picture source."
    ),
    "assets/images/suzuko-gallery2.jpg": (
        "PNG bytes use a .jpg name and index.html declares old dimensions."
    ),
    "assets/images/suzuko-gallery2.webp": (
        "PNG bytes use a .webp name; it is the current picture source."
    ),
}

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
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
        self._json_ld_depth = 0
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
        if tag == "script":
            self.scripts.append(values)
            if values.get("type", "").lower() == "application/ld+json":
                self._json_ld_depth += 1
                self._json_ld_parts = []
        if tag == "link":
            self.links.append(values)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld_depth:
            self.json_ld.append("".join(self._json_ld_parts))
            self._json_ld_depth -= 1
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
        reason = KNOWN_IMAGE_ISSUES.get(relative)
        if reason and dt.date.today() <= ALLOWLIST_EXPIRY:
            self.warning(
                f"KNOWN ISSUE until {ALLOWLIST_EXPIRY}: {relative}: {message} Reason: {reason}"
            )
        elif reason:
            self.error(
                f"EXPIRED KNOWN ISSUE: {relative}: {message} Reason was: {reason}"
            )
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
    return Path(unquote(urlsplit(value).path))


def image_signature_and_size(path: Path) -> tuple[str, tuple[int, int] | None]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return "png", (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))
    if data.startswith(b"\xff\xd8\xff"):
        offset = 2
        sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8))
        sof_markers |= set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in sof_markers:
                return "jpeg", (
                    int.from_bytes(data[offset + 5:offset + 7], "big"),
                    int.from_bytes(data[offset + 3:offset + 5], "big"),
                )
            offset += max(length, 2)
        return "jpeg", None
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp", None
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif", (int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little"))
    return "unknown", None


def expected_image_format(path: Path) -> str | None:
    return {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".gif": "gif"}.get(path.suffix.lower())


def check_local_reference(current: Path, value: str, reporter: Reporter) -> None:
    for candidate in value.split(","):
        url = candidate.strip().split()[0] if candidate.strip() else ""
        local = local_reference(url)
        if local is None:
            continue
        resolved = (current.parent / local).resolve()
        try:
            relative = resolved.relative_to(ROOT)
        except ValueError:
            reporter.error(f"{current.relative_to(ROOT)}: reference escapes repository: {url}")
            continue
        if not resolved.exists():
            case_matches = [
                item for item in ROOT.rglob("*")
                if item.as_posix().lower() == resolved.as_posix().lower()
            ]
            suffix = " (case mismatch)" if case_matches else ""
            reporter.error(
                f"{current.relative_to(ROOT)}: missing local file: {relative.as_posix()}{suffix}"
            )


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
            reporter.error(f"{relative}: img is missing alt: {image.get('src', '(no src)')}")
        src = image.get("src", "")
        local = local_reference(src)
        if local:
            image_path = (path.parent / local).resolve()
            if image_path.exists() and image.get("width") and image.get("height"):
                _, actual = image_signature_and_size(image_path)
                if actual and (str(actual[0]) != image["width"] or str(actual[1]) != image["height"]):
                    reporter.image_issue(
                        image_path,
                        f"HTML dimensions {image['width']}x{image['height']} do not match {actual[0]}x{actual[1]}",
                    )

    for target in parser.target_blanks:
        rel_tokens = set(target.get("rel", "").lower().split())
        if "noopener" not in rel_tokens:
            reporter.error(f"{relative}: target=_blank without rel=noopener: {target.get('href', '')}")

    for _, value in parser.references:
        check_local_reference(path, value, reporter)

    for script in parser.scripts:
        src = script.get("src", "")
        if src and is_external(src):
            reporter.error(f"{relative}: external JavaScript is not allowed: {src}")

    for link in parser.links:
        rel_tokens = set(link.get("rel", "").lower().split())
        href = link.get("href", "")
        if "stylesheet" in rel_tokens and is_external(href):
            reporter.error(f"{relative}: external stylesheet is not allowed: {href}")
        if rel_tokens & {"preconnect", "dns-prefetch"} and is_external(href):
            reporter.error(f"{relative}: external network hint is not allowed: {href}")

    for json_ld in parser.json_ld:
        try:
            json.loads(json_ld)
        except json.JSONDecodeError as error:
            reporter.error(f"{relative}: invalid JSON-LD: {error.msg}")

    if path.name == "index.html":
        meta_by_name = {meta.get("name", "").lower(): meta.get("content", "") for meta in parser.metas}
        meta_by_property = {meta.get("property", "").lower(): meta.get("content", "") for meta in parser.metas}
        required_names = ("viewport", "description")
        required_properties = ("og:title", "og:type", "og:url", "og:image", "og:description", "og:site_name")
        if "<meta charset=" not in text.lower():
            reporter.error("index.html: required meta charset is missing")
        if "<title>" not in text.lower():
            reporter.error("index.html: required title is missing")
        for name in required_names:
            if not meta_by_name.get(name):
                reporter.error(f"index.html: required meta name={name} is missing")
        for name in required_properties:
            if not meta_by_property.get(name):
                reporter.error(f"index.html: required meta property={name} is missing")
        canonical = next(
            (link.get("href", "") for link in parser.links if link.get("rel", "").lower() == "canonical"),
            "",
        )
        if canonical != OFFICIAL_URL:
            reporter.error(f"index.html: canonical must be {OFFICIAL_URL}")
        if meta_by_property.get("og:url") != OFFICIAL_URL:
            reporter.error(f"index.html: og:url must be {OFFICIAL_URL}")

        og_image = meta_by_property.get("og:image", "")
        if og_image.startswith(OFFICIAL_URL):
            image_path = ROOT / unquote(og_image.removeprefix(OFFICIAL_URL))
            if image_path.exists():
                _, actual = image_signature_and_size(image_path)
                og_width = meta_by_property.get("og:image:width")
                og_height = meta_by_property.get("og:image:height")
                if actual and og_width and og_height and (og_width != str(actual[0]) or og_height != str(actual[1])):
                    reporter.image_issue(
                        image_path,
                        f"OG dimensions {og_width}x{og_height} do not match {actual[0]}x{actual[1]}",
                    )

    for url in re.findall(r"https?://[^\s\"'<>]+", text):
        if url.startswith("http://"):
            reporter.error(f"{relative}: insecure http URL: {url}")
        if "abcderp2.github.io" in url and not url.startswith(OFFICIAL_URL):
            reporter.error(f"{relative}: official URL typo or wrong base path: {url}")


def check_images(reporter: Reporter) -> None:
    image_directory = ROOT / "assets" / "images"
    if not image_directory.exists():
        reporter.error("assets/images directory is missing")
        return
    for path in sorted(item for item in image_directory.rglob("*") if item.is_file()):
        if path.name == ".keep":
            continue
        actual_format, _ = image_signature_and_size(path)
        expected_format = expected_image_format(path)
        if expected_format and actual_format != expected_format:
            reporter.image_issue(
                path,
                f"file extension expects {expected_format}, but bytes are {actual_format}",
            )
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            reporter.error(f"{path.relative_to(ROOT)}: image is larger than {MAX_IMAGE_BYTES} bytes")
        elif size > WARN_IMAGE_BYTES:
            reporter.warning(f"{path.relative_to(ROOT)}: image is larger than {WARN_IMAGE_BYTES} bytes")


def check_css(reporter: Reporter) -> None:
    for path in ROOT.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        for url in re.findall(r"url\(\s*['\"]?([^'\"\s)]+)", text, flags=re.IGNORECASE):
            if url.startswith("http://"):
                reporter.error(f"{relative}: insecure http CSS URL: {url}")
            elif is_external(url):
                reporter.error(f"{relative}: external font or asset is not allowed: {url}")


def check_secrets(reporter: Reporter) -> None:
    allowed_suffixes = {".html", ".css", ".md", ".txt", ".yml", ".yaml", ".py", ".xml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
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
