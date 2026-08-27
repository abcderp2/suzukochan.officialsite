# 鈴子ちゃん公式サイト

GitHub Pagesで公開している、オリジナルキャラクター「鈴子ちゃん」の公式ウェブサイトです。

## 公式サイト

https://abcderp2.github.io/suzukochan.officialsite/

## 掲載内容

- 鈴子ちゃんの公式ビジュアルとプロフィール
- 鈴子ちゃんの誕生経緯
- White Wing病院の設定と公式外観ビジュアル
- 更新情報
- 二次創作と画像利用のガイドライン
- 公式SNSと関連リンク
- 日本語版と英語版

White Wing病院の公式名称は「White Wing Hospital」「ホワイトウィング病院」「White Wing病院」の3表記です。主に「White Wing病院」を使用します。青い翼と白い翼は、どちらも公式のシンボルマークです。公開する病院ビジュアルは外観1点のみとし、院内画像は公開しません。鈴子ちゃんの利用ガイドラインを適用します。

## 技術構成

無料プランのAIとエントリークラスのスマートフォンまたはタブレットでも保守しやすい、軽量な静的サイトです。スマートフォン、タブレット、PCなど、画面幅の異なるデバイスで閲覧できるレスポンシブ構成です。

- HTML5
- CSS3
- Python標準ライブラリによる読み取り専用検査
- 外部Actionを使わないGitHub Actions
- GitHub Pages
- JavaScript、ビルドツール、パッケージ管理、有料API、外部CDN、アクセス解析なし

## セキュリティとプライバシー

サイトの公開と保守に、OpenAI APIキーを含むAPIキー、アクセストークン、パスワードは不要です。認証情報を会話、Issue、Pull Request、コードへ貼り付けません。

画像は公開前に[画像メタデータクリーナー](https://abcderp2.github.io/Exif/)で処理し、Exif、GPS、XMP、ICCなどの不要な付加情報を残しません。自動検査でも画像形式、容量、メタデータ、ローカル参照を確認します。

標準検査は次の2つです。

```text
python3 -I scripts/check_site.py
python3 -I scripts/security_audit.py --history
```

脆弱性の報告方法と秘密情報漏えい時の対応は[SECURITY.md](SECURITY.md)に集約しています。

## 保守

正本の保守手順は[MAINTENANCE.md](MAINTENANCE.md)です。変更前のバックアップブランチ、作業ブランチ、検査、Pull Request、Squash and merge、公開確認、Revertまでを省略せず記載しています。

保守をAIへ依頼するときは、最初に`MAINTENANCE.md`と今回の依頼内容を渡します。セキュリティ関連の変更では`SECURITY.md`も渡します。

## 機械向け補助ファイル

- `robots.txt`
- `sitemap.xml`
- `llms.txt`

AIの訪問と、公開情報を検索結果や利用者向けAI回答で適切に紹介することを歓迎します。鈴子ちゃんのキャラクター、設定、公式画像、White Wing病院の公式外観ビジュアルなどの具体的な利用は、公式サイトのガイドラインと`LICENSE`に従います。

## 公式リンク

- YouTube: https://www.youtube.com/@abc-l2g6k/shorts
- note: https://note.com/stocktrading0_ai/n/n6883256131d2?app_launch=false
- X 鈴子ちゃん: https://x.com/suzuko_ai_
- X 作者 鈴木: https://x.com/stocktrading0
- pixiv: https://www.pixiv.net/users/116903703
- GitHub: https://github.com/abcderp2/suzukochan.officialsite
- ニコニコ動画: https://sp.nicovideo.jp/user/141613837/shorts?sortKey=registeredAt&sortOrder=desc

<!-- GitHub Pages redeploy trigger: 2026-08-27 11:52 -->
