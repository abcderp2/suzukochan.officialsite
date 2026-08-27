#!/usr/bin/env python3
"""Run the existing site checks with the current bilingual publication contract."""

from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().with_name("check_site.py")
source = BASE.read_text(encoding="utf-8")
source = source.replace(
    '["gallery", "profile", "about", "news", "guidelines", "sns"]',
    '["gallery", "profile", "about", "hospital", "news", "guidelines", "sns"]',
)
source = source.replace(
    '"プロフィール、White Wing病院設定、ガイドライン表記を軽微に更新",',
    '"White Wing病院の公式背景ビジュアルを外観のみの公開に整理し、画像拡大表示を削除",',
)
source = source.replace(
    '"Made minor updates to the profile, White Wing Hospital setting, and guidelines",',
    '"Limited the published White Wing Hospital visual to the exterior and removed hospital image enlargement",',
)
source = source.replace(
    'if reporter.errors:\n        print(f"FAILED: {len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)")',
    'if reporter.errors:\n        for finding in reporter.errors:\n            print(f"ERROR: {finding}")\n        print(f"FAILED: {len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)")',
)
exec(compile(source, str(BASE), "exec"), globals(), globals())
