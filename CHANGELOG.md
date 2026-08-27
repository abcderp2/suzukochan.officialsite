# 保守変更履歴

このファイルには、リポジトリの保守方法や技術構成に関する変更を記録します。読者向けの更新情報を公開ページへ追加するためのものではありません。

記入形式

`YYYY-MM-DD | 変更理由 | 対象ファイル | 戻す単位`

2026-08-27 | White Wing病院の公開ビジュアルを外観1点に整理し、入口ホール・院内廊下・診察室の画像を非公開化。病院画像のCSS拡大表示を削除し、日英ページ、README、更新情報を整合。既存のレスポンシブ構成を維持 | index.html, en.html, assets/css/style.css, assets/images/white-wing-hospital/*.webp, README.md, CHANGELOG.md | SquashコミットをRevert

2026-08-08 | AIの訪問と公開情報の検索・紹介を歓迎しつつ、一般的なAIモデル学習については許可も拒否も表明しない中立方針へ日英ページ、robots.txt、llms.txt、README、保守文書を統一。GPTBot、ClaudeBot、Google-Extendedの個別Disallowを削除し、個人端末内のLoRA利用と学習モデル公開禁止の既存ガイドラインは維持 | index.html, en.html, robots.txt, llms.txt, README.md, MAINTENANCE.md, CHANGELOG.md | SquashコミットをRevert

2026-08-07 | 404ページだけに残っていた古いCSSキャッシュ識別子を公開ページと統一し、将来の不一致を静的検査で防止 | 404.html, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert

2026-08-06 | 英語版のWhite Wing病院の主表記を日本語と英語で分け、英訳を自然な表現へ調整。日英のメタ説明文へWhite Wing病院を追加し、全ナビゲーションリンクの最小高さを44pxへ統一。language-switch専用CSSと重複指定を.nav aへ統合し、検査を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert

2026-08-06 | CSS拡大表示をモーダルと誤認させない名前付き領域へ整理し、各拡大画像を対応するサムネイル直後へ配置してキーボードの開閉順と戻り先を明確化。画像ファイルは変更せず、JSON-LDから架空住所を削除して人物と病院が架空であることを日英で明記。公開検査へ病院セクションと背景画像4点を追加、更新情報検査をpとliの両方へ対応 | index.html, en.html, assets/css/style.css, scripts/check_site.py, .github/workflows/live-site-check.yml, MAINTENANCE.md, CHANGELOG.md | SquashコミットをRevert

2026-08-06 | 公式画像ファイルの転載・再配布と二次創作作品公開の区分を日英ガイドラインとLICENSEで明確化。White Wing病院背景にも同じ区分を適用。既存の必須`check`ジョブ内でGit履歴を含むSecurity auditも実行し、個別検査結果を制御文字除去と文字数制限付きで再表示 | index.html, en.html, LICENSE, scripts/check_site.py, .github/workflows/check-site.yml, SECURITY.md, MAINTENANCE.md, CHANGELOG.md | SquashコミットをRevert

2026-08-06 | White Wing病院の公式名称3種、主表記、青と白の翼シンボル、鈴子ちゃんと同一の画像利用条件を日英ページへ明記。メタデータ除去済みWebP 4点を、外部依存とJavaScriptを使わない2列レスポンシブギャラリーとCSS拡大表示で追加。初心者向け保守手順とREADMEを統合更新 | index.html, en.html, 404.html, assets/css/style.css, assets/images/white-wing-hospital/*.webp, README.md, MAINTENANCE.md, llms.txt, CHANGELOG.md | SquashコミットをRevert

2026-07-31 | OpenAI APIキーなどの認証情報を不要とする運用を明文化し、現在のファイルと取得済みGit履歴を外部Action、外部パッケージ、有料APIなしで検査する読み取り専用監査を追加。認証情報ファイルの除外、漏えい時の無効化手順、初心者向け保守案内も統合 | scripts/security_audit.py, .github/workflows/security-audit.yml, SECURITY.md, .gitignore, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-24 | AI向けメッセージが既存ガイドラインの個人利用許諾を打ち消さないよう、メッセージ自体は追加許諾を与えず具体的利用はガイドラインに従うことを明確化 | index.html, en.html, llms.txt, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-24 | ガイドラインへ短いAI向けメッセージを日英で追加し、検索・利用者向けAI回答は歓迎、AI訪問メッセージ自体はモデル学習その他の追加許諾を与えない権利方針へ補助ファイルとREADMEを統一 | index.html, en.html, robots.txt, llms.txt, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-24 | 公式サイトを見に来る人に不要な画像処理ページと公開リンクを除去し、既存画像のメタデータ検査は維持。今後の画像処理先を別サイトへ変更 | image-privacy.html, assets/js/image-privacy.js, index.html, en.html, assets/css/style.css, scripts/check_site.py, MAINTENANCE.md, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-24 | 既存画像のメタデータを除去し、端末内で画像を処理するページと公開前検査を追加。公開ページの更新情報は変更しない | image-privacy.html, assets/js/image-privacy.js, assets/images/*.webp, index.html, en.html, assets/css/style.css, scripts/check_site.py, MAINTENANCE.md, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-23 | 無料プランのAIとスマートフォンでも確認漏れや検査原因を把握しやすくするため、PRテンプレート、検査の注釈と概要、週次・手動の公開生存確認、AIクローラー許可の明示を追加。公開HTML、CSS、画像は変更しない | .github/pull_request_template.md, .github/workflows/check-site.yml, .github/workflows/live-site-check.yml, robots.txt, CHANGELOG.md | SquashコミットをRevert
2026-07-20 | 7月18日のCSS変更後も古いキャッシュ識別子が残っていたため、全HTMLのスタイルシート参照を同じ識別子へ更新 | index.html, en.html, 404.html, CHANGELOG.md | SquashコミットをRevert
2026-07-18 | 英語版と日本語・英語切り替え機能を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert
2026-07-16 | 分散していた保守説明をMAINTENANCE.mdへ統合し、無料プランのAIとスマートフォン、タブレットを前提とした手順、AIによるコード解析と学習の扱い、復旧方法を明確化。古い参照例外を検査コードから削除し、説明書の再分散を検査対象へ追加 | MAINTENANCE.md, README.md, CHANGELOG.md, scripts/check_site.py, AI_HANDOFF.md, FACTS.md, PUBLISH_CHECKLIST.md | SquashコミットをRevert
2026-07-15 | AIとスマートフォンで保守しやすい手順、自動検査、404ページを追加 | AI_HANDOFF.md, MAINTENANCE.md, FACTS.md, PUBLISH_CHECKLIST.md, CHANGELOG.md, 404.html, .nojekyll, scripts/check_site.py, .github/workflows/check-site.yml | SquashコミットをRevert
