# キャラクター画像アニメーター

1枚のPNG、JPEG、WebP画像へ単純な動きを付け、GIFまたは現在フレームのPNGとして保存する静的Webツールです。

公開URL

https://abcderp2.github.io/suzukochan.officialsite/tools/character-animator/

## 設計上の境界

- 画像処理とGIF生成はブラウザ内だけで行います。
- 外部API、外部CDN、外部ライブラリ、広告、アクセス解析、Cookieを使用しません。
- 画像そのものはlocalStorage、設定JSON、Service Workerのキャッシュへ保存しません。
- 入力はPNG、JPEG、WebPだけです。SVGなどの能動的コンテンツは読み込みません。
- 入力は15MB、縦横8192px、合計3200万画素までです。
- GIFは256、360、480px、2秒から6秒、10、12、15fpsの範囲に制限します。
- GIF生成は可能な環境ではWeb Workerへ分離し、1フレームずつ処理します。ローカルファイルなどWorkerが使えない環境ではメインスレッドの互換モードへ切り替えます。

## 公開版の使い方

1. 公開URLをブラウザで開きます。
2. 画像を選びます。
3. 動き、サイズ、背景を調整します。
4. GIFを保存します。
5. 保存に失敗した場合は256×256、3秒、10fpsへ下げます。

ホーム画面へ追加した場合、初回読み込み後はService Workerのアプリ用キャッシュからオフライン起動できます。ブラウザのデータ削除後は再度オンラインで開く必要があります。

## ローカル版の使い方

GitHubのリポジトリ画面からCode、Download ZIPを選び、ZIPを展開します。その後、`tools/character-animator/index.html`をブラウザで開きます。

Androidの一般的なブラウザではローカルHTMLとして動作します。ローカルファイルからWeb Workerを起動できないブラウザでは、自動的に互換モードを使います。

iPhoneとiPadは、ファイル管理アプリのプレビューがJavaScriptを実行しない場合があります。その場合は公開版をSafariで開き、共有メニューからホーム画面に追加してください。追加後はオフラインでも起動できます。

ローカルサーバーを利用できる環境では、リポジトリ直下で次を実行します。

```bash
python3 -m http.server 8000
```

その後、`http://localhost:8000/tools/character-animator/`を開きます。

## ファイルの役割

- `index.html`: 画面構造とセキュリティポリシー
- `app.css`: レスポンシブ表示、タッチ操作、アクセシビリティ
- `app.js`: 入力検査、プレビュー、設定、PNGとGIFの書き出し
- `gif-encoder.js`: 固定パレットとGIF89aエンコーダー
- `gif-worker.js`: GIF処理を画面処理から分離
- `manifest.webmanifest`: ホーム画面追加用の情報
- `sw.js`: アプリ用静的ファイルだけをオフラインキャッシュ

ファイルを増やす前に、既存ファイルへ小さく追加できないか確認します。フレームワーク、パッケージ管理、ビルド手順は追加しません。

## 検査

リポジトリ直下で次を実行します。

```bash
python3 -I scripts/check_site.py
node --check tools/character-animator/gif-encoder.js
node --check tools/character-animator/gif-worker.js
node --check tools/character-animator/app.js
node --check tools/character-animator/sw.js
node scripts/test_gif_encoder.mjs
```

GIFテストは外部パッケージを使わず、生成した複数フレームGIFを解析して、復号結果が元の色番号と一致することを確認します。

## 手動確認

- 320px程度の狭い画面で横スクロールしない
- タッチ対象が小さすぎない
- PNG、JPEG、WebPを読み込める
- SVG、15MB超、巨大画像を拒否する
- 6種類の動きが再生される
- 指ドラッグと矢印キーで位置を変更できる
- 透明、白、黒、緑、任意色の背景を選べる
- GIFとPNGを保存できる
- GIF生成を中止できる
- 設定JSONの保存と読み込みができる
- 再読み込み後も設定値だけが復元され、画像は復元されない
- 開発者ツールのNetworkで外部送信がない
- オフライン再読み込みで画面が起動する

## 更新と戻し方

公開ファイルを変更したときは、HTML内の`?v=1`、`sw.js`の`CACHE_NAME`、`APP_SHELL`を同じ変更単位で更新します。古いキャッシュを残したまま一部だけ更新しません。

不具合が見つかった場合は、今回のSquashコミットをRevertします。Service Worker更新後も古い表示が残る場合は、ブラウザのサイトデータを削除して公開URLを再度開きます。
