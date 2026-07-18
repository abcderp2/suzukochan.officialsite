# 保守変更履歴

このファイルには、リポジトリの保守方法や技術構成に関する変更を記録します。読者向けの更新情報を公開ページへ追加するためのものではありません。

記入形式

`YYYY-MM-DD | 変更理由 | 対象ファイル | 戻す単位`

2026-07-18 | 英語版と日本語・英語切り替え機能を追加 | index.html, en.html, assets/css/style.css, scripts/check_site.py, CHANGELOG.md | SquashコミットをRevert
2026-07-16 | 分散していた保守説明をMAINTENANCE.mdへ統合し、無料プランのAIとスマートフォン、タブレットを前提とした手順、AIによるコード解析と学習の扱い、復旧方法を明確化。古い参照例外を検査コードから削除し、説明書の再分散を検査対象へ追加 | MAINTENANCE.md, README.md, CHANGELOG.md, scripts/check_site.py, AI_HANDOFF.md, FACTS.md, PUBLISH_CHECKLIST.md | SquashコミットをRevert
2026-07-15 | AIとスマートフォンで保守しやすい手順、自動検査、404ページを追加 | AI_HANDOFF.md, MAINTENANCE.md, FACTS.md, PUBLISH_CHECKLIST.md, CHANGELOG.md, 404.html, .nojekyll, scripts/check_site.py, .github/workflows/check-site.yml | SquashコミットをRevert
