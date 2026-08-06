#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("apply_en_copy_nav_once.py")
text = path.read_text(encoding="utf-8")
old = '        "2026-08-06 | 英語版のWhite Wing病院の主表記を日本語と英語で分け、英訳を自然な表現へ調整。日英のメタ説明文へWhite Wing病院を追加し、全ナビゲーションリンクの最小高さを44pxへ統一。language-switch専用CSSと重複指定を.nav aへ統合し、検査を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert\\n\\n"\n    text = replace_exact(text, marker, marker + entry)'
new = '        "2026-08-06 | 英語版のWhite Wing病院の主表記を日本語と英語で分け、英訳を自然な表現へ調整。日英のメタ説明文へWhite Wing病院を追加し、全ナビゲーションリンクの最小高さを44pxへ統一。language-switch専用CSSと重複指定を.nav aへ統合し、検査を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert\\n\\n"\n    )\n    text = replace_exact(text, marker, marker + entry)'
if text.count(old) != 1:
    raise RuntimeError("target syntax fragment not found exactly once")
path.write_text(text.replace(old, new), encoding="utf-8")
