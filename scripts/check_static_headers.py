#!/usr/bin/env python3
"""Reject static HTML that pretends unsupported response headers are active."""

from __future__ import annotations

import html.parser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MetaParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.permissions_policy_meta = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        if values.get("http-equiv", "").strip().lower() == "permissions-policy":
            self.permissions_policy_meta += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def main() -> int:
    failures: list[str] = []
    for path in sorted(ROOT.rglob("*.html")):
        parser = MetaParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if parser.permissions_policy_meta:
            failures.append(path.relative_to(ROOT).as_posix())

    if failures:
        print("ERROR: unsupported Permissions-Policy http-equiv meta found in: " + ", ".join(failures))
        return 1

    print("Static response-header policy check: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
