# 保守変更履歴

このファイルには、リポジトリの保守方法や技術構成に関する変更を記録します。読者向けの更新情報を公開ページへ追加するためのものではありません。

記入形式

`YYYY-MM-DD | 変更理由 | 対象ファイル | 戻す単位`

2026-07-24 | 公式サイトを見に来る人に不要な画像処理ページと公開リンクを除去し、既存画像のメタデータ検査は維持。今後の画像処理先を別サイトへ変更 | image-privacy.html, assets/js/image-privacy.js, index.html, en.html, assets/css/style.css, scripts/check_site.py, MAINTENANCE.md, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-24 | 既存画像のメタデータを除去し、端末内で画像を処理するページと公開前検査を追加。公開ページの更新情報は変更しない | image-privacy.html, assets/js/image-privacy.js, assets/images/*.webp, index.html, en.html, assets/css/style.css, scripts/check_site.py, MAINTENANCE.md, README.md, CHANGELOG.md | SquashコミットをRevert

2026-07-23 | 無料プランのAIとスマートフォンでも確認漏れや検査原因を把握しやすくするため、PRテンプレート、検査の注釈と概要、週次・手動の公開生存確認、AIクローラー許可の明示を追加。公開HTML、CSS、画像は変更しない | .github/pull_request_template.md, .github/workflows/check-site.yml, .github/workflows/live-site-check.yml, robots.txt, CHANGELOG.md | SquashコミットをRevert
2026-07-20 | 7月18日のCSS変更後も古いキャッシュ識別子が残っていたため、全HTMLのスタイルシート参照を同じ識別子へ更新 | index.html, en.html, 404.html, CHANGELOG.md | SquashコミットをRevert
2026-07-18 | 英語版と日本語・英語切り替え機能を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert
2026-07-16 | 分散していた保守説明をMAINTENANCE.mdへ統合し、無料プランのAIとスマートフォン、タブレットを前提とした手順、AIによるコード解析と学習の扱い、復旧方法を明確化。古い参照例外を検査コードから削除し、説明書の再分散を検査対象へ追加 | MAINTENANCE.md, README.md, CHANGELOG.md, scripts/check_site.py, AI_HANDOFF.md, FACTS.md, PUBLISH_CHECKLIST.md | SquashコミットをRevert
2026-07-15 | AIとスマートフォンで保守しやすい手順、自動検査、404ページを追加 | AI_HANDOFF.md, MAINTENANCE.md, FACTS.md, PUBLISH_CHECKLIST.md, CHANGELOG.md, 404.html, .nojekyll, scripts/check_site.py, .github/workflows/check-site.yml | SquashコミットをRevert
