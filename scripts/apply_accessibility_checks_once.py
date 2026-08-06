#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    write(path, text.replace(old, new, 1))


def refresh_json_ld_hash(path: str) -> None:
    text = read(path)
    match = re.search(
        r'<script type="application/ld\+json">(?P<body>.*?)</script>',
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise SystemExit(f"{path}: JSON-LD script not found")
    json.loads(match.group("body"))
    digest = base64.b64encode(
        hashlib.sha256(match.group("body").encode("utf-8")).digest()
    ).decode("ascii")
    replacement = f"script-src 'sha256-{digest}';"
    text, count = re.subn(
        r"script-src 'sha256-[^']+';",
        replacement,
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"{path}: CSP script hash not found")
    write(path, text)


def reorganize_lightboxes(path: str) -> None:
    text = read(path)
    gallery_pattern = re.compile(
        r'      <div class="hospital-gallery"[^>]*>\n(?P<body>.*?)\n      </div>\n',
        flags=re.DOTALL,
    )
    gallery_match = gallery_pattern.search(text)
    if gallery_match is None:
        raise SystemExit(f"{path}: hospital gallery not found")

    figure_pattern = re.compile(
        r'        <figure class="hospital-card">\n.*?\n        </figure>',
        flags=re.DOTALL,
    )
    figures = figure_pattern.findall(gallery_match.group("body"))

    lightbox_pattern = re.compile(
        r'      <div\n'
        r'        id="(?P<id>hospital-(?:exterior|lobby|corridor|exam-room)-lightbox)"\n'
        r'        class="lightbox"\n'
        r'        role="dialog"\n'
        r'        aria-labelledby="(?P<label>[^"]+)"\n'
        r'        tabindex="-1"\n'
        r'      >\n.*?\n      </div>\n',
        flags=re.DOTALL,
    )
    lightbox_matches = list(lightbox_pattern.finditer(text))
    expected_ids = [
        "hospital-exterior-lightbox",
        "hospital-lobby-lightbox",
        "hospital-corridor-lightbox",
        "hospital-exam-room-lightbox",
    ]
    found_ids = [match.group("id") for match in lightbox_matches]
    if len(figures) != 4 or found_ids != expected_ids:
        raise SystemExit(
            f"{path}: expected four ordered figures and lightboxes, found {len(figures)} and {found_ids}"
        )

    transformed_boxes: dict[str, str] = {}
    for match in lightbox_matches:
        lightbox_id = match.group("id")
        thumb_id = lightbox_id.removesuffix("-lightbox") + "-thumb"
        box = match.group(0)
        box = box.replace("      <div\n", "      <section\n", 1)
        box = box.replace('        role="dialog"\n', "", 1)
        box = box.replace('        tabindex="-1"\n', "", 1)
        box = box.replace('href="#hospital"', f'href="#{thumb_id}"')
        box = box[:-len("      </div>\n")] + "      </section>\n"
        box = "\n".join(("  " + line) if line else line for line in box.rstrip("\n").split("\n"))
        transformed_boxes[lightbox_id] = box

    for match in reversed(lightbox_matches):
        text = text[:match.start()] + text[match.end():]

    gallery_match = gallery_pattern.search(text)
    if gallery_match is None:
        raise SystemExit(f"{path}: hospital gallery disappeared during transformation")

    new_children: list[str] = []
    for figure, lightbox_id in zip(figures, expected_ids, strict=True):
        thumb_id = lightbox_id.removesuffix("-lightbox") + "-thumb"
        old_anchor = f'<a class="hospital-thumb" href="#{lightbox_id}"'
        new_anchor = (
            f'<a id="{thumb_id}" class="hospital-thumb" href="#{lightbox_id}" '
            f'aria-controls="{lightbox_id}"'
        )
        if figure.count(old_anchor) != 1:
            raise SystemExit(f"{path}: thumbnail anchor not found for {lightbox_id}")
        figure = figure.replace(old_anchor, new_anchor, 1)
        new_children.append(figure + "\n" + transformed_boxes[lightbox_id])

    opening_end = text.find("\n", gallery_match.start()) + 1
    opening = text[gallery_match.start():opening_end]
    new_gallery = opening + "\n".join(new_children) + "\n      </div>\n"
    text = text[:gallery_match.start()] + new_gallery + text[gallery_match.end():]
    write(path, text)


JA_JSON_OLD = '''    "worksFor":{
      "@type":"Hospital",
      "name":"White Wing病院",
      "alternateName":["White Wing Hospital","ホワイトウィング病院"],
      "address":{
        "@type":"PostalAddress",
        "addressCountry":"JP",
        "addressLocality":"架空の街",
        "streetAddress":"架空の番地"
      }
    },
    "url":"https://abcderp2.github.io/suzukochan.officialsite/",
    "description":"架空のWhite Wing病院に勤める若手看護師。",
'''
JA_JSON_NEW = '''    "worksFor":{
      "@type":"Hospital",
      "name":"White Wing病院",
      "alternateName":["White Wing Hospital","ホワイトウィング病院"],
      "description":"鈴子ちゃんの世界観に登場する架空の病院。"
    },
    "url":"https://abcderp2.github.io/suzukochan.officialsite/",
    "description":"架空のキャラクターであり、架空のWhite Wing病院に勤める若手看護師。",
'''
EN_JSON_OLD = '''    "worksFor":{
      "@type":"Hospital",
      "name":"White Wing Hospital",
      "alternateName":["White Wing病院","ホワイトウィング病院"],
      "address":{
        "@type":"PostalAddress",
        "addressCountry":"JP",
        "addressLocality":"Fictional city",
        "streetAddress":"Fictional street address"
      }
    },
    "url":"https://abcderp2.github.io/suzukochan.officialsite/en.html",
    "description":"A young nurse working at the fictional White Wing Hospital.",
'''
EN_JSON_NEW = '''    "worksFor":{
      "@type":"Hospital",
      "name":"White Wing Hospital",
      "alternateName":["White Wing病院","ホワイトウィング病院"],
      "description":"A fictional hospital in Suzuko-chan's world."
    },
    "url":"https://abcderp2.github.io/suzukochan.officialsite/en.html",
    "description":"A fictional character and young nurse working at the fictional White Wing Hospital.",
'''

replace_once("index.html", JA_JSON_OLD, JA_JSON_NEW)
replace_once("en.html", EN_JSON_OLD, EN_JSON_NEW)
reorganize_lightboxes("index.html")
reorganize_lightboxes("en.html")
refresh_json_ld_hash("index.html")
refresh_json_ld_hash("en.html")

replace_once(
    "assets/css/style.css",
    '''  background: #eef2f6;
  text-decoration: none;
}
''',
    '''  background: #eef2f6;
  text-decoration: none;
  scroll-margin-top: 16px;
}
''',
)
replace_once(
    "assets/css/style.css",
    '''.hospital-thumb:focus-visible,
.lightbox-close:focus-visible{
''',
    '''.hospital-thumb:focus-visible,
.hospital-thumb:target,
.lightbox-close:focus-visible{
''',
)

replace_once(
    "scripts/check_site.py",
    '''        elif tag == "li" and self._section_id == "news":
            self._news_item = {"datetime": ""}
            self._news_text = []
''',
    '''        elif tag in {"p", "li"} and self._section_id == "news" and self._news_item is None:
            self._news_item = {"datetime": "", "tag": tag}
            self._news_text = []
''',
)
replace_once(
    "scripts/check_site.py",
    '''        elif tag == "li" and self._news_item is not None:
            self._news_item["text"] = " ".join("".join(self._news_text).split())
            self.news_items.append(self._news_item)
            self._news_item = None
            self._news_text = []
''',
    '''        elif self._news_item is not None and tag == self._news_item.get("tag"):
            self._news_item["text"] = " ".join("".join(self._news_text).split())
            self.news_items.append(self._news_item)
            self._news_item = None
            self._news_text = []
''',
)
replace_once(
    "scripts/check_site.py",
    '''    if not parser.news_items:
        reporter.error(f"{name}: update history is missing")
    else:
        latest = parser.news_items[0]
        if latest.get("datetime") != "2026-07-18" or expected_news_text not in latest.get("text", ""):
            reporter.error(f"{name}: latest update history is incorrect")
''',
    '''    if not parser.news_items:
        reporter.error(f"{name}: update history is missing")
    else:
        news_tags = {item.get("tag", "") for item in parser.news_items}
        if not {"p", "li"}.issubset(news_tags):
            reporter.error(f"{name}: update history must support both p and li entries")
        latest = parser.news_items[0]
        if latest.get("datetime") != "2026-08-06" or expected_news_text not in latest.get("text", ""):
            reporter.error(f"{name}: latest update history is incorrect")
''',
)
replace_once(
    "scripts/check_site.py",
    '''    if BILINGUAL_TRANSLATION_MARKERS.search(text):
        reporter.error(f"{name}: external translation service reference is not allowed")

    if expected_lang == "en":
''',
    '''    if parser.json_ld:
        try:
            structured_data = json.loads(parser.json_ld[0])
        except json.JSONDecodeError:
            structured_data = {}
        works_for = structured_data.get("worksFor", {})
        if isinstance(works_for, dict) and "address" in works_for:
            reporter.error(f"{name}: fictional hospital JSON-LD must not contain an address")
        fictional_marker = "架空" if expected_lang == "ja" else "fictional"
        person_description = str(structured_data.get("description", ""))
        hospital_description = str(works_for.get("description", "")) if isinstance(works_for, dict) else ""
        if fictional_marker.lower() not in person_description.lower():
            reporter.error(f"{name}: JSON-LD person description must state that the character is fictional")
        if fictional_marker.lower() not in hospital_description.lower():
            reporter.error(f"{name}: JSON-LD hospital description must state that the hospital is fictional")

    if BILINGUAL_TRANSLATION_MARKERS.search(text):
        reporter.error(f"{name}: external translation service reference is not allowed")

    if expected_lang == "en":
''',
)
replace_once(
    "scripts/check_site.py",
    '''        "英語版と日本語・英語切り替え機能を追加",
''',
    '''        "公式画像と二次創作作品の利用区分を明確化",
''',
)
replace_once(
    "scripts/check_site.py",
    '''        "Added an English version and Japanese–English language switching",
''',
    '''        "Clarified the distinction between official image files and derivative works",
''',
)

replace_once(
    "MAINTENANCE.md",
    '''PCでは2列、幅700px以下では1列です。画像を押すと同じページ上へCSSだけで拡大表示し、閉じるリンクまたは背景のタップで戻ります。外部スクリプト、JavaScriptライブラリ、画像CDNを追加しません。
''',
    '''PCでは2列、幅700px以下では1列です。画像を押すと同じページ上へCSSだけで拡大表示します。拡大画像は完全なモーダルダイアログとは宣言せず、ページ内の名前付き領域として扱います。キーボードではサムネイルをEnterで開き、Tabで直後の閉じるリンクへ移動し、Enterで同じサムネイルへ戻ります。背景のタップでも同じサムネイルへ戻ります。外部スクリプト、JavaScriptライブラリ、画像CDNを追加しません。
''',
)

changelog = read("CHANGELOG.md")
entry = "2026-08-06 | CSS拡大表示をモーダルと誤認させない名前付き領域へ整理し、各拡大画像を対応するサムネイル直後へ配置してキーボードの開閉順と戻り先を明確化。画像ファイルは変更せず、JSON-LDから架空住所を削除して人物と病院が架空であることを日英で明記。公開検査へ病院セクションと背景画像4点を追加し、更新情報検査をpとliの両方へ対応 | index.html, en.html, assets/css/style.css, scripts/check_site.py, .github/workflows/live-site-check.yml, MAINTENANCE.md, CHANGELOG.md | SquashコミットをRevert\n\n"
marker = "`YYYY-MM-DD | 変更理由 | 対象ファイル | 戻す単位`\n\n"
if changelog.count(marker) != 1:
    raise SystemExit("CHANGELOG.md: insertion marker not found exactly once")
write("CHANGELOG.md", changelog.replace(marker, marker + entry, 1))

for page in ("index.html", "en.html"):
    text = read(page)
    if 'role="dialog"' in text or 'tabindex="-1"\n      >' in text:
        raise SystemExit(f"{page}: old dialog semantics remain")
    if text.count('class="lightbox"') != 4:
        raise SystemExit(f"{page}: expected four lightboxes")
    if '"address"' in re.search(
        r'<script type="application/ld\+json">(?P<body>.*?)</script>',
        text,
        flags=re.DOTALL,
    ).group("body"):
        raise SystemExit(f"{page}: JSON-LD address remains")
