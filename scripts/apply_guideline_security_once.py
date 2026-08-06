#!/usr/bin/env python3
"""Apply the explicitly approved guideline and CI hardening changes once."""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


ja_basic_old = '''        <p>
          「鈴子ちゃん」は作者の思想や哲学を反映させながら育成しているキャラクターです。<br>
          本ガイドラインを遵守していただける限り、個人の方が趣味の範囲で行う創作活動（イラスト、漫画、小説、動画、AI生成など）を歓迎いたします。
        </p>
'''
ja_basic_new = ja_basic_old + '''
        <p>
          公式画像ファイルをそのまま、または実質的に同一の状態で転載・再配布することは禁止します。一方、公式画像を参考にしたり、制作過程で利用したりした二次創作作品は、本ガイドラインの範囲内で公開できます。商用利用、年齢制限作品、なりすまし、学習モデルの公開・共有・配布はできません。White Wing病院の公式背景ビジュアルにも同じ区分を適用します。
        </p>
'''
replace_once("index.html", ja_basic_old, ja_basic_new)

ja_redistribution_old = '''          <li>
            <strong>画像の再配布</strong><br>
            作者が作成・公開した画像を、そのままの状態で二次配布・転載することは禁止します。
          </li>
'''
ja_redistribution_new = '''          <li>
            <strong>公式画像ファイルの転載・再配布</strong><br>
            作者が作成・公開した公式画像ファイルを、そのまま、またはトリミング、圧縮、色調変更などを施しても実質的に同一の状態で転載・再配布することは禁止します。White Wing病院の公式背景ビジュアルにも同じ区分を適用します。
          </li>
'''
replace_once("index.html", ja_redistribution_old, ja_redistribution_new)

ja_news_old = '''      <p><time datetime="2026-08-06">2026-08-06</time> White Wing病院の公式背景ビジュアル4点を追加</p>
'''
ja_news_new = '''      <p><time datetime="2026-08-06">2026-08-06</time> 公式画像と二次創作作品の利用区分を明確化</p>
      <p><time datetime="2026-08-06">2026-08-06</time> White Wing病院の公式背景ビジュアル4点を追加</p>
'''
replace_once("index.html", ja_news_old, ja_news_new)

en_basic_old = '''        <p>
          "Suzuko-chan" is a character being developed while reflecting the author's thoughts and philosophy.<br>
          As long as you follow these guidelines, personal creative activities within the scope of hobbies, including illustrations, manga, novels, videos, and AI-generated works, are welcome.
        </p>
'''
en_basic_new = en_basic_old + '''
        <p>
          Official image files may not be reposted or redistributed in their original form or in a substantially identical form. Derivative works that refer to official images or use them during the creation process may be published within these guidelines. Commercial use, age-restricted works, impersonation, and the publication, sharing, or distribution of training models are prohibited. The same distinction applies to the official White Wing Hospital background visuals.
        </p>
'''
replace_once("en.html", en_basic_old, en_basic_new)

en_redistribution_old = '''          <li>
            <strong>Redistributing images</strong><br>
            It is prohibited to redistribute or repost, in their original form, images created and published by the author.
          </li>
'''
en_redistribution_new = '''          <li>
            <strong>Reposting or redistributing official image files</strong><br>
            Official image files created and published by the author may not be reposted or redistributed in their original form or in a substantially identical form, including versions that have only been cropped, compressed, or color-adjusted. The same distinction applies to the official White Wing Hospital background visuals.
          </li>
'''
replace_once("en.html", en_redistribution_old, en_redistribution_new)

en_news_old = '''      <p><time datetime="2026-08-06">2026-08-06</time> Added four official White Wing Hospital background visuals</p>
'''
en_news_new = '''      <p><time datetime="2026-08-06">2026-08-06</time> Clarified the distinction between official image files and derivative works</p>
      <p><time datetime="2026-08-06">2026-08-06</time> Added four official White Wing Hospital background visuals</p>
'''
replace_once("en.html", en_news_old, en_news_new)

license_text = '''このプロジェクトはデュアルライセンス制です。

---

1. キャラクター「鈴子ちゃん」について

鈴子ちゃんのデザイン、設定、イラストは、著作権により保護されています。

著作権所有者： 鈴木

使用許諾： サイト内の「ガイドライン」をお読みください。
https://abcderp2.github.io/suzukochan.officialsite/#guidelines

以下は特に重要です：

- 全年齢向けのファンアートは歓迎します
- 公式画像を参考にしたり、制作過程で利用したりした二次創作作品は、ガイドラインの範囲内で公開できます
- 公式画像ファイルをそのまま、または実質的に同一の状態で転載・再配布することは禁止です
- R-18・R-18G表現は禁止です
- 無断での商用利用は禁止です
- 学習モデル（LoRA等）の公開・共有・配布は禁止です
- キャラクターを自分の創作だと偽ることや、公式になりすますことは禁止です
- White Wing病院の公式背景ビジュアルにも同じ区分を適用します

詳細は公式サイトのガイドラインをご確認ください。

---

2. ウェブサイトコード（HTML・CSS）について

以下の MIT License に従います。

MIT License

Copyright (c) 2026 Suzuki (Author of Suzuko-chan Official Site)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

3. 画像アセットについて

assets/images/ 内の画像には、キャラクター「鈴子ちゃん」の公式画像と、White Wing病院の公式背景ビジュアルが含まれます。

- 公式画像ファイルの転載・再配布：そのまま、またはトリミング、圧縮、色調変更などを施しても実質的に同一の状態で行うことは禁止
- 二次創作作品の公開：公式画像を参考にしたり、制作過程で利用したりした作品は、サイト内ガイドラインの範囲で可能
- 商用利用：無断では禁止
- 年齢制限作品：R-18・R-18Gは禁止
- なりすまし、自作発言：禁止
- 学習モデル：個人端末内での作成・利用はガイドラインの範囲で可能ですが、公開・共有・配布・販売は禁止
- White Wing病院の公式背景ビジュアル：上記と同じ区分を適用

詳細はガイドラインをご確認ください。

---

4. 免責事項（Disclaimer）

本プロジェクト（キャラクター「鈴子ちゃん」、ウェブサイトのコード、画像アセット等のすべて）を利用したことによって生じた、いかなるトラブル、損失、または損害に対しても、著作者（鈴木）は一切の責任を負いません。
利用者は、すべて自己責任において本プロジェクトを利用するものとします。

---

使用時の確認事項

本プロジェクトを利用する場合：

1. ウェブサイトのコードのみを利用する場合
   → MIT License に従う必要があります

2. キャラクター「鈴子ちゃん」や画像アセットを利用する場合
   → サイトのガイドラインに従う必要があります

3. 両方を利用する場合
   → 両方のルールに従う必要があります

---

更新日：2026年8月6日
'''
Path("LICENSE").write_text(license_text, encoding="utf-8")

check_site_old = '''    print("Static site and maintenance check")

    if reporter.errors:
        print(f"FAILED: {len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)")
'''
check_site_new = '''    print("Static site and maintenance check")

    # Findings contain only internally generated categories and paths. Remove
    # control characters and cap each line before writing it to CI logs.
    for warning in reporter.warnings:
        message = re.sub(r"[\\x00-\\x1f\\x7f]", " ", warning)[:500]
        print(f"WARNING: {message}")
    for error in reporter.errors:
        message = re.sub(r"[\\x00-\\x1f\\x7f]", " ", error)[:500]
        print(f"ERROR: {message}")

    if reporter.errors:
        print(f"FAILED: {len(reporter.errors)} error(s), {len(reporter.warnings)} warning(s)")
'''
replace_once("scripts/check_site.py", check_site_old, check_site_new)

required_workflow = '''name: Site checks

on:
  pull_request:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: site-checks-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

defaults:
  run:
    shell: bash --noprofile --norc -euo pipefail {0}

jobs:
  check:
    runs-on: ubuntu-24.04
    timeout-minutes: 8
    steps:
      - name: Check out the triggering ref and reachable history without an external action
        env:
          REPOSITORY: ${{ github.repository }}
          REF: ${{ github.ref }}
          EXPECTED_SHA: ${{ github.sha }}
          SERVER_URL: ${{ github.server_url }}
        run: |
          umask 077
          git init .
          git remote add origin "${SERVER_URL}/${REPOSITORY}.git"
          git fetch --no-tags --prune origin \\
            "${REF}" \\
            '+refs/heads/*:refs/remotes/origin/*'
          git checkout --detach "${EXPECTED_SHA}"
          test "$(git rev-parse HEAD)" = "${EXPECTED_SHA}"

      - name: Check static site files
        run: |
          log_file="${RUNNER_TEMP}/site-check.log"
          status=0
          python3 -I scripts/check_site.py >"${log_file}" 2>&1 || status=$?

          escape_command() {
            local value="$1"
            value="${value//'%'/'%25'}"
            value="${value//$'\\r'/'%0D'}"
            value="${value//$'\\n'/'%0A'}"
            printf '%s' "${value}"
          }

          while IFS= read -r line; do
            case "${line}" in
              ERROR:\\ *)
                message="${line#ERROR: }"
                printf '::error title=Site checks::%s\\n' "$(escape_command "${message}")"
                ;;
              WARNING:\\ *)
                message="${line#WARNING: }"
                printf '::warning title=Site checks::%s\\n' "$(escape_command "${message}")"
                ;;
            esac
          done <"${log_file}"

          if [ "${status}" -eq 0 ]; then
            result="Passed"
          else
            result="Failed"
          fi

          {
            echo "## Site checks"
            echo
            echo "- Result: **${result}**"
            echo "- Commit: \\`${GITHUB_SHA}\\`"
            echo "- Command: \\`python3 -I scripts/check_site.py\\`"
            echo
            echo "### Output"
            sed 's/^/    /' "${log_file}"
          } >>"${GITHUB_STEP_SUMMARY}"

          cat "${log_file}"
          exit "${status}"

      - name: Run the required security audit
        run: |
          log_file="${RUNNER_TEMP}/security-audit.log"
          status=0
          python3 -I scripts/security_audit.py --history >"${log_file}" 2>&1 || status=$?

          escape_command() {
            local value="$1"
            value="${value//'%'/'%25'}"
            value="${value//$'\\r'/'%0D'}"
            value="${value//$'\\n'/'%0A'}"
            printf '%s' "${value}"
          }

          while IFS= read -r line; do
            case "${line}" in
              ERROR:\\ *)
                message="${line#ERROR: }"
                printf '::error title=Required security audit::%s\\n' "$(escape_command "${message}")"
                ;;
            esac
          done <"${log_file}"

          if [ "${status}" -eq 0 ]; then
            result="Passed"
          else
            result="Failed"
          fi

          {
            echo "## Required security audit"
            echo
            echo "- Result: **${result}**"
            echo "- Commit: \\`${GITHUB_SHA}\\`"
            echo "- Current tree: checked"
            echo "- Reachable Git history: checked"
            echo "- Command: \\`python3 -I scripts/security_audit.py --history\\`"
            echo
            echo "### Output"
            sed 's/^/    /' "${log_file}"
          } >>"${GITHUB_STEP_SUMMARY}"

          cat "${log_file}"
          exit "${status}"
'''
Path(".github/workflows/check-site.yml").write_text(required_workflow, encoding="utf-8")

security_old = '''- `python3 -I scripts/check_site.py`
- `python3 -I scripts/security_audit.py --history`

`security_audit.py`は、現在のファイルと取得済みのGit履歴を調べ、OpenAI、GitHub、AWS、Google、Slack、npm、Stripeなどの既知の認証情報形式、秘密鍵、認証情報らしい代入、危険なファイル名を検出します。検出時は値を表示せず、種類、場所、照合用の短いハッシュだけを出力します。
'''
security_new = '''- `python3 -I scripts/check_site.py`
- `python3 -I scripts/security_audit.py --history`

mainブランチの必須ステータス検査`check`は、上記2つを同じジョブ内で実行します。どちらか一方でも失敗した場合は必須検査が失敗し、マージできません。独立した`Security audit`ワークフローも追加確認として維持します。

`security_audit.py`は、現在のファイルと取得済みのGit履歴を調べ、OpenAI、GitHub、AWS、Google、Slack、npm、Stripeなどの既知の認証情報形式、秘密鍵、認証情報らしい代入、危険なファイル名を検出します。検出時は値を表示せず、種類、場所、照合用の短いハッシュだけを出力します。
'''
replace_once("SECURITY.md", security_old, security_new)

maintenance_old = '''鈴子ちゃんのキャラクター、設定、イラスト、White Wing病院の公式背景ビジュアルはコードとは別の条件です。公開ページのガイドラインと`LICENSE`に従います。個人の端末内での画像利用や追加学習モデルの作成と利用は、現行ガイドラインの範囲で扱います。画像の再配布、学習モデルの公開、共有、配布、販売は行いません。
'''
maintenance_new = '''鈴子ちゃんのキャラクター、設定、イラスト、White Wing病院の公式背景ビジュアルはコードとは別の条件です。公開ページのガイドラインと`LICENSE`に従います。公式画像ファイルをそのまま、または実質的に同一の状態で転載・再配布することは禁止します。公式画像を参考にしたり制作過程で利用したりした二次創作作品は、ガイドラインの範囲で公開できます。個人の端末内での画像利用や追加学習モデルの作成と利用は現行ガイドラインの範囲で扱い、商用利用、年齢制限作品、なりすまし、学習モデルの公開・共有・配布・販売は行いません。White Wing病院の公式背景ビジュアルにも同じ区分を適用します。
'''
replace_once("MAINTENANCE.md", maintenance_old, maintenance_new)

changelog_marker = '''2026-08-06 | White Wing病院の公式名称3種、主表記、青と白の翼シンボル、鈴子ちゃんと同一の画像利用条件を日英ページへ明記。メタデータ除去済みWebP 4点を、外部依存とJavaScriptを使わない2列レスポンシブギャラリーとCSS拡大表示で追加。初心者向け保守手順とREADMEを統合更新 | index.html, en.html, 404.html, assets/css/style.css, assets/images/white-wing-hospital/*.webp, README.md, MAINTENANCE.md, llms.txt, CHANGELOG.md | SquashコミットをRevert
'''
changelog_entry = '''2026-08-06 | 公式画像ファイルの転載・再配布と二次創作作品公開の区分を日英ガイドラインとLICENSEで明確化。White Wing病院背景にも同じ区分を適用。既存の必須`check`ジョブ内でGit履歴を含むSecurity auditも実行し、個別検査結果を制御文字除去と文字数制限付きで再表示 | index.html, en.html, LICENSE, scripts/check_site.py, .github/workflows/check-site.yml, SECURITY.md, MAINTENANCE.md, CHANGELOG.md | SquashコミットをRevert

'''
replace_once("CHANGELOG.md", changelog_marker, changelog_entry + changelog_marker)
