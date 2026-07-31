#!/usr/bin/env python3
"""Read-only security, portability, and maintenance checks for the static site."""

from __future__ import annotations

import base64
import hashlib
import html.parser
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
OFFICIAL_URL = "https://abcderp2.github.io/suzukochan.officialsite/"
REPOSITORY_URL = "https://github.com/abcderp2/suzukochan.officialsite"
PROJECT_PATH = "/suzukochan.officialsite/"
TOOL_PATH = Path("tools/character-animator/index.html")
TOOL_URL = OFFICIAL_URL + "tools/character-animator/"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
WARN_IMAGE_BYTES = 1 * 1024 * 1024

REQUIRED_MAINTENANCE_FILES = {"MAINTENANCE.md", "CHANGELOG.md"}
OBSOLETE_MAINTENANCE_FILES = {"AI_HANDOFF.md", "FACTS.md", "PUBLISH_CHECKLIST.md"}
FORBIDDEN_HTML_TAGS = {"base", "embed", "form", "iframe", "object"}
ALLOWED_INLINE_SCRIPT_TYPES = {"application/ld+json"}

STANDARD_CSP = {
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

TOOL_CSP = {
    "default-src": {"'none'"},
    "base-uri": {"'none'"},
    "connect-src": {"'none'"},
    "font-src": {"'none'"},
    "form-action": {"'none'"},
    "frame-ancestors": {"'none'"},
    "frame-src": {"'none'"},
    "img-src": {"'self'", "blob:"},
    "manifest-src": {"'self'"},
    "media-src": {"'none'"},
    "object-src": {"'none'"},
    "script-src": {"'self'"},
    "style-src": {"'self'"},
    "worker-src": {"'self'"},
}

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")),
    ("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
)


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


class SiteParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.ids: list[str] = []
        self.sections: list[str] = []
        self.images: list[dict[str, str]] = []
        self.sources: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []
        self.anchors: list[dict[str, str]] = []
        self.references: list[tuple[str, str]] = []
        self.target_blanks: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self.event_handlers: list[tuple[str, str]] = []
        self.inline_styles: list[str] = []
        self.forbidden_tags: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag in FORBIDDEN_HTML_TAGS:
            self.forbidden_tags.append(tag)
        for name in values:
            if name.startswith("on"):
                self.event_handlers.append((tag, name))
        if "style" in values or tag == "style":
            self.inline_styles.append(tag)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "section":
            self.sections.append(values.get("id", ""))
        if tag == "img":
            self.images.append(values)
        if tag == "source":
            self.sources.append(values)
        if tag == "input":
            self.inputs.append(values)
        if tag == "a":
            self.anchors.append(values)
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
                self._in_json_ld = True
                self._json_ld_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._json_ld_parts))
            self._in_json_ld = False
            self._json_ld_parts = []


class ParsedPage:
    def __init__(self, path: Path, parser: SiteParser, text: str) -> None:
        self.path = path
        self.parser = parser
        self.text = text


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
        path = path[len(PROJECT_PATH):]
    elif path.startswith("/"):
        return Path("__outside_project__")
    if not path or path.endswith("/"):
        path += "index.html"
    return Path(path)


def check_reference(current: Path, tag: str, value: str, reporter: Reporter) -> None:
    lowered = value.strip().lower()
    if lowered.startswith(("data:", "javascript:", "vbscript:")):
        reporter.error(f"{relative(current)}: forbidden URL scheme in {tag}: {value}")
        return

    candidates = value.split(",") if tag in {"img", "source"} else [value]
    for candidate in candidates:
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


def meta_value(parser: SiteParser, key: str, attribute: str = "name") -> str:
    for meta in parser.metas:
        if meta.get(attribute, "").lower() == key.lower():
            return meta.get("content", "")
    return ""


def link_values(parser: SiteParser, relation: str) -> list[dict[str, str]]:
    return [
        link for link in parser.links
        if relation in {token.lower() for token in link.get("rel", "").split()}
    ]


def check_csp(path: Path, parser: SiteParser, text: str, reporter: Reporter) -> None:
    name = relative(path)
    values = [
        meta.get("content", "")
        for meta in parser.metas
        if meta.get("http-equiv", "").lower() == "content-security-policy"
    ]
    if len(values) != 1:
        reporter.error(f"{name}: exactly one Content-Security-Policy meta is required")
        return
    try:
        policy = parse_csp(values[0])
    except ValueError as error:
        reporter.error(f"{name}: invalid Content-Security-Policy: {error}")
        return

    if path.relative_to(ROOT) == TOOL_PATH:
        expected = TOOL_CSP
    else:
        expected = dict(STANDARD_CSP)
        expected["script-src"] = {script_hash(block) for block in parser.json_ld} or {"'none'"}

    for directive, tokens in expected.items():
        if policy.get(directive) != tokens:
            reporter.error(f"{name}: CSP {directive} must be {' '.join(sorted(tokens))}")
    allowed_directives = set(expected) | {"upgrade-insecure-requests"}
    for directive in sorted(set(policy) - allowed_directives):
        reporter.error(f"{name}: unexpected CSP directive: {directive}")
    if policy.get("upgrade-insecure-requests") != set():
        reporter.error(f"{name}: CSP upgrade-insecure-requests is required without a value")

    lowered = text.lower()
    csp_position = lowered.find('http-equiv="content-security-policy"')
    resource_positions = [
        position for position in (lowered.find("<link"), lowered.find("<script")) if position >= 0
    ]
    if resource_positions and csp_position > min(resource_positions):
        reporter.error(f"{name}: CSP meta must appear before resource-loading elements")


def check_html(path: Path, reporter: Reporter) -> ParsedPage:
    text = path.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(text)
    name = relative(path)
    is_tool = path.relative_to(ROOT) == TOOL_PATH

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
        tokens = set(target.get("rel", "").lower().split())
        for required in ("noopener", "noreferrer"):
            if required not in tokens:
                reporter.error(f"{name}: target=_blank without rel={required}")
    for tag, value in parser.references:
        check_reference(path, tag, value, reporter)

    for script in parser.scripts:
        src = script.get("src", "")
        script_type = script.get("type", "").lower()
        if is_tool:
            if not src:
                reporter.error(f"{name}: executable scripts must be separate local files")
            elif is_external(src):
                reporter.error(f"{name}: external script is not allowed: {src}")
            if script_type not in {"", "text/javascript"}:
                reporter.error(f"{name}: unsupported script type: {script_type}")
            if "defer" not in script:
                reporter.error(f"{name}: tool scripts must use defer")
        else:
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

    if meta_value(parser, "referrer").lower() != "no-referrer":
        reporter.error(f"{name}: referrer policy must be no-referrer")
    for meta in parser.metas:
        if meta.get("http-equiv", "").lower() == "refresh":
            reporter.error(f"{name}: meta refresh is not allowed")
    check_csp(path, parser, text, reporter)

    for url in re.findall(r"https?://[^\s\"'<>]+", text):
        if url.startswith("http://"):
            reporter.error(f"{name}: insecure http URL: {url}")
        if "abcderp2.github.io" in url and not url.startswith(OFFICIAL_URL):
            reporter.error(f"{name}: official URL typo: {url}")

    return ParsedPage(path, parser, text)


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


def check_images(reporter: Reporter) -> None:
    directory = ROOT / "assets" / "images"
    if not directory.exists():
        reporter.error("assets/images directory is missing")
        return
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        expected = expected_image_format(path)
        if expected:
            actual = image_signature(path)
            if actual != expected:
                reporter.error(f"{relative(path)}: extension expects {expected}, bytes are {actual}")
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            reporter.error(f"{relative(path)}: image is larger than 5 MiB")
        elif size > WARN_IMAGE_BYTES:
            reporter.warning(f"{relative(path)}: image is larger than 1 MiB")
        for finding in image_metadata_findings(path):
            reporter.error(f"{relative(path)}: image metadata is present ({finding})")


def check_css(reporter: Reporter) -> None:
    for path in ROOT.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"@import\s", text, flags=re.IGNORECASE):
            reporter.error(f"{relative(path)}: CSS @import is not allowed")
        for url in re.findall(r"url\(\s*['\"]?([^'\"\s)]+)", text, flags=re.IGNORECASE):
            if url.startswith(("data:", "http://", "https://")) or is_external(url):
                reporter.error(f"{relative(path)}: external or data CSS URL: {url}")


def check_javascript(reporter: Reporter) -> None:
    tool_directory = ROOT / "tools" / "character-animator"
    required = {
        "README.md",
        "app.css",
        "app.js",
        "gif-encoder.js",
        "gif-worker.js",
        "index.html",
        "manifest.webmanifest",
        "sw.js",
    }
    if not tool_directory.is_dir():
        reporter.error("tools/character-animator: directory is missing")
        return
    actual = {path.name for path in tool_directory.iterdir() if path.is_file()}
    for name in sorted(required - actual):
        reporter.error(f"tools/character-animator/{name}: required file is missing")
    for name in sorted(actual - required):
        reporter.error(f"tools/character-animator/{name}: unexpected file increases maintenance scope")

    size_limits = {
        "index.html": 20_000,
        "app.css": 16_000,
        "app.js": 40_000,
        "gif-encoder.js": 16_000,
        "gif-worker.js": 5_000,
        "sw.js": 5_000,
        "manifest.webmanifest": 3_000,
        "README.md": 12_000,
    }
    for name, limit in size_limits.items():
        path = tool_directory / name
        if path.is_file() and path.stat().st_size > limit:
            reporter.error(f"{relative(path)}: exceeds the maintainability budget of {limit} bytes")

    forbidden = (
        ("dynamic code execution", re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(")),
        ("HTML string injection", re.compile(r"\.(?:innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\(")),
        ("document.write", re.compile(r"document\.write\s*\(")),
        ("network socket", re.compile(r"\b(?:WebSocket|EventSource|XMLHttpRequest)\b")),
        ("analytics beacon", re.compile(r"sendBeacon\s*\(")),
        ("source map reference", re.compile(r"sourceMappingURL=")),
    )
    for path in sorted(tool_directory.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        if "'use strict';" not in text[:300]:
            reporter.error(f"{relative(path)}: use strict is required")
        for label, pattern in forbidden:
            if pattern.search(text):
                reporter.error(f"{relative(path)}: forbidden {label}")
        for url in re.findall(r"https?://[^\s\"'`]+", text):
            reporter.error(f"{relative(path)}: external URL is not allowed: {url}")
        if "fetch(" in text and path.name != "sw.js":
            reporter.error(f"{relative(path)}: network fetch is not allowed")
        if "importScripts(" in text and path.name != "gif-worker.js":
            reporter.error(f"{relative(path)}: importScripts is only allowed in gif-worker.js")
    worker_text = (tool_directory / "gif-worker.js").read_text(encoding="utf-8")
    if "importScripts('./gif-encoder.js')" not in worker_text:
        reporter.error("tools/character-animator/gif-worker.js: encoder import must remain local and fixed")


def check_tool_contract(page: ParsedPage, reporter: Reporter) -> None:
    parser = page.parser
    name = relative(page.path)
    if parser.html_lang != "ja":
        reporter.error(f"{name}: html lang must be ja")
    required_ids = {
        "imageInput", "previewCanvas", "playButton", "centerButton", "flipButton",
        "resetButton", "preset", "amplitude", "speed", "rotation", "pulse", "zoom",
        "outputSize", "duration", "fps", "backgroundMode", "backgroundColor",
        "exportGifButton", "exportPngButton", "cancelExportButton", "exportProgress",
        "status", "exportSettingsButton", "importSettingsInput",
    }
    for element_id in sorted(required_ids - set(parser.ids)):
        reporter.error(f"{name}: required control id is missing: {element_id}")
    file_inputs = [item for item in parser.inputs if item.get("type", "").lower() == "file"]
    image_inputs = [item for item in file_inputs if item.get("id") == "imageInput"]
    if len(image_inputs) != 1:
        reporter.error(f"{name}: exactly one imageInput file control is required")
    else:
        accept = image_inputs[0].get("accept", "").lower()
        for required in ("image/png", "image/jpeg", "image/webp"):
            if required not in accept:
                reporter.error(f"{name}: imageInput must accept {required}")
        if "svg" in accept or "image/*" in accept:
            reporter.error(f"{name}: broad or SVG image input is not allowed")
    canonical = [link.get("href", "") for link in link_values(parser, "canonical")]
    if canonical != [TOOL_URL]:
        reporter.error(f"{name}: canonical must be {TOOL_URL}")
    manifests = [link.get("href", "") for link in link_values(parser, "manifest")]
    if manifests != ["manifest.webmanifest"]:
        reporter.error(f"{name}: one local manifest is required")
    scripts = {script.get("src", "") for script in parser.scripts}
    if scripts != {"gif-encoder.js?v=1", "app.js?v=1"}:
        reporter.error(f"{name}: script set or cache version is incorrect")
    required_text = (
        "画像はアップロードされません",
        "外部API、広告、アクセス解析、アカウント登録は使用しません",
        "GIFを保存",
        "設定JSONを保存",
    )
    for marker in required_text:
        if marker not in page.text:
            reporter.error(f"{name}: required user-facing statement is missing: {marker}")

    manifest_path = ROOT / "tools" / "character-animator" / "manifest.webmanifest"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        reporter.error(f"tools/character-animator/manifest.webmanifest: invalid JSON: {error}")
    else:
        expected_manifest = {"start_url": "./", "scope": "./", "display": "standalone", "lang": "ja"}
        for key, value in expected_manifest.items():
            if manifest.get(key) != value:
                reporter.error(f"tools/character-animator/manifest.webmanifest: {key} must be {value}")
        if "icons" in manifest:
            reporter.error("tools/character-animator/manifest.webmanifest: icons require an explicit asset review")

    sw_path = ROOT / "tools" / "character-animator" / "sw.js"
    if sw_path.is_file():
        sw = sw_path.read_text(encoding="utf-8")
        required_sw = (
            "const CACHE_NAME = 'character-animator-v1';",
            "requestUrl.origin !== self.location.origin",
            "event.request.method !== 'GET'",
            "'./app.css?v=1'",
            "'./gif-encoder.js?v=1'",
            "'./app.js?v=1'",
        )
        for marker in required_sw:
            if marker not in sw:
                reporter.error(f"tools/character-animator/sw.js: required cache safeguard is missing: {marker}")

    readme_path = ROOT / "tools" / "character-animator" / "README.md"
    if readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        for marker in (TOOL_URL, "ローカル版の使い方", "node scripts/test_gif_encoder.mjs", "SquashコミットをRevert"):
            if marker not in readme:
                reporter.error(f"tools/character-animator/README.md: required maintenance fact is missing: {marker}")


def image_sources(parser: SiteParser) -> list[str]:
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


def external_anchors(parser: SiteParser) -> set[str]:
    local_official = {OFFICIAL_URL, OFFICIAL_URL + "en.html", TOOL_URL}
    return {
        anchor.get("href", "")
        for anchor in parser.anchors
        if is_external(anchor.get("href", "")) and anchor.get("href", "") not in local_official
    }


def check_bilingual_pages(pages: dict[Path, ParsedPage], reporter: Reporter) -> None:
    ja_path = ROOT / "index.html"
    en_path = ROOT / "en.html"
    if ja_path not in pages or en_path not in pages:
        reporter.error("index.html and en.html are required")
        return
    ja = pages[ja_path].parser
    en = pages[en_path].parser
    if ja.html_lang != "ja":
        reporter.error("index.html: html lang must be ja")
    if en.html_lang != "en":
        reporter.error("en.html: html lang must be en")
    expected_sections = ["gallery", "profile", "about", "news", "guidelines", "sns"]
    if ja.sections != expected_sections:
        reporter.error("index.html: section ids or order are incorrect")
    if en.sections != expected_sections:
        reporter.error("en.html: section ids or order are incorrect")
    if image_sources(ja) != image_sources(en):
        reporter.error("index.html and en.html: image references do not match")
    if [link.get("href", "") for link in link_values(ja, "stylesheet")] != [
        link.get("href", "") for link in link_values(en, "stylesheet")
    ]:
        reporter.error("index.html and en.html: stylesheet references do not match")
    if external_anchors(ja) != external_anchors(en):
        reporter.error("index.html and en.html: external links do not match")
    if "".join(en.title_parts).strip() != "Suzuko-chan Official Site":
        reporter.error("en.html: title is not English")

    expected_urls = {"ja": OFFICIAL_URL, "en": OFFICIAL_URL + "en.html", "x-default": OFFICIAL_URL}
    for filename, parser, canonical_url in (
        ("index.html", ja, OFFICIAL_URL),
        ("en.html", en, OFFICIAL_URL + "en.html"),
    ):
        canonical = [link.get("href", "") for link in link_values(parser, "canonical")]
        if canonical != [canonical_url]:
            reporter.error(f"{filename}: canonical URL is incorrect")
        alternates = {
            link.get("hreflang", ""): link.get("href", "")
            for link in link_values(parser, "alternate")
        }
        if alternates != expected_urls:
            reporter.error(f"{filename}: alternate hreflang links are incorrect")

    ja_switch = [a for a in ja.anchors if "language-switch" in a.get("class", "").split()]
    en_switch = [a for a in en.anchors if "language-switch" in a.get("class", "").split()]
    if len(ja_switch) != 1 or ja_switch[0].get("href") != "en.html" or ja_switch[0].get("hreflang") != "en":
        reporter.error("index.html: English language switch is incorrect")
    if len(en_switch) != 1 or en_switch[0].get("href") != "index.html" or en_switch[0].get("hreflang") != "ja":
        reporter.error("en.html: Japanese language switch is incorrect")


def check_sitemap(reporter: Reporter) -> None:
    path = ROOT / "sitemap.xml"
    if not path.is_file():
        reporter.error("sitemap.xml is missing")
        return
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        reporter.error(f"sitemap.xml: invalid XML: {error}")
        return
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {element.text or "" for element in root.findall("s:url/s:loc", namespace)}
    expected = {OFFICIAL_URL, OFFICIAL_URL + "en.html", TOOL_URL}
    if locations != expected:
        reporter.error("sitemap.xml: URLs must contain only the Japanese, English, and animator pages")


def check_secrets(reporter: Reporter) -> None:
    suffixes = {
        ".conf", ".css", ".env", ".html", ".ini", ".js", ".json", ".md", ".mjs",
        ".py", ".toml", ".txt", ".webmanifest", ".xml", ".yaml", ".yml",
    }
    ignored_parts = {".git", ".venv", "__pycache__", "node_modules"}
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
    workflows = sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))) if directory.exists() else []
    if not workflows:
        reporter.error(".github/workflows: no workflow file found")
        return
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        for snippet in (
            "permissions:\n  contents: read",
            "timeout-minutes:",
            "shell: bash --noprofile --norc -euo pipefail {0}",
            "python3 -I scripts/check_site.py",
        ):
            if snippet not in text:
                reporter.error(f"{relative(path)}: missing workflow hardening setting: {snippet.splitlines()[0]}")
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

    check_workflow = ROOT / ".github" / "workflows" / "check-site.yml"
    if check_workflow.is_file():
        text = check_workflow.read_text(encoding="utf-8")
        for snippet in (
            "node --check",
            "node scripts/test_gif_encoder.mjs",
        ):
            if snippet not in text:
                reporter.error(f".github/workflows/check-site.yml: missing JavaScript validation: {snippet}")


def check_gitignore(reporter: Reporter) -> None:
    path = ROOT / ".gitignore"
    if not path.exists():
        reporter.error(".gitignore is missing")
        return
    entries = {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {
        ".env", ".env.*", "*.jks", "*.key", "*.p12", "*.pem", "*.pfx",
        "*.py[cod]", "__pycache__/", "id_ed25519*", "id_rsa*",
    }
    for entry in sorted(required - entries):
        reporter.error(f".gitignore: missing sensitive-file pattern: {entry}")


def check_repository_shape(reporter: Reporter) -> None:
    forbidden_names = {"node_modules", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            reporter.error(f"{relative(path)}: symbolic links are not allowed")
        if path.name in forbidden_names:
            reporter.error(f"{relative(path)}: package dependency files are not allowed")
        if path.is_file() and path.name in {".env", "id_ed25519", "id_rsa"}:
            reporter.error(f"{relative(path)}: sensitive file must not be committed")


def check_maintenance_contract(reporter: Reporter) -> None:
    for filename in sorted(REQUIRED_MAINTENANCE_FILES):
        if not (ROOT / filename).is_file():
            reporter.error(f"{filename}: required maintenance file is missing")
    for filename in sorted(OBSOLETE_MAINTENANCE_FILES):
        if (ROOT / filename).exists():
            reporter.error(f"{filename}: obsolete instructions must remain consolidated")

    readme_path = ROOT / "README.md"
    if not readme_path.is_file():
        reporter.error("README.md is missing")
    else:
        text = readme_path.read_text(encoding="utf-8")
        for marker in ("MAINTENANCE.md", TOOL_URL, "ローカル", "外部API"):
            if marker not in text:
                reporter.error(f"README.md: required maintenance or tool fact is missing: {marker}")

    manual_path = ROOT / "MAINTENANCE.md"
    if manual_path.is_file():
        text = manual_path.read_text(encoding="utf-8")
        for fact in (OFFICIAL_URL, REPOSITORY_URL, "python3 -I scripts/check_site.py", "Squash and merge", "Revert"):
            if fact not in text:
                reporter.error(f"MAINTENANCE.md: required fact is missing: {fact}")

    changelog_path = ROOT / "CHANGELOG.md"
    if changelog_path.is_file():
        text = changelog_path.read_text(encoding="utf-8")
        if "2026-07-31" not in text or "character-animator" not in text:
            reporter.error("CHANGELOG.md: animator release entry for 2026-07-31 is missing")


def main() -> int:
    reporter = Reporter()
    pages: dict[Path, ParsedPage] = {}
    for path in sorted(ROOT.rglob("*.html")):
        pages[path] = check_html(path, reporter)

    tool_page_path = ROOT / TOOL_PATH
    if tool_page_path in pages:
        check_tool_contract(pages[tool_page_path], reporter)
    else:
        reporter.error(f"{TOOL_PATH.as_posix()}: tool page is missing")

    check_bilingual_pages(pages, reporter)
    check_sitemap(reporter)
    check_images(reporter)
    check_css(reporter)
    check_javascript(reporter)
    check_secrets(reporter)
    check_workflows(reporter)
    check_gitignore(reporter)
    check_repository_shape(reporter)
    check_maintenance_contract(reporter)

    print("Static site, animator, security, and maintenance check")
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
