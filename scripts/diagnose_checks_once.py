#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

path = Path(__file__).with_name("check_site.py").resolve()
spec = importlib.util.spec_from_file_location("site_checks", path)
if spec is None or spec.loader is None:
    raise SystemExit("Unable to load site checks")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def check_html_files(reporter: object) -> None:
    for item in sorted(module.ROOT.rglob("*.html")):
        module.check_html(item, reporter)


checks = (
    ("html", check_html_files),
    ("images", module.check_images),
    ("css", module.check_css),
    ("secrets", module.check_secrets),
    ("workflows", module.check_workflows),
    ("gitignore", module.check_gitignore),
    ("repository", module.check_repository_shape),
    ("maintenance", module.check_maintenance_contract),
    ("bilingual", module.check_bilingual_pages),
)

for name, check in checks:
    reporter = module.Reporter()
    check(reporter)
    print(
        f"DIAGNOSTIC {name}: "
        f"{len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)"
    )
