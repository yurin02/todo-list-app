# Todo List App

## Overview
Google スプレッドシートをデータストアにしたTodoリスト管理Webアプリ。認証なし、URLを知っていれば誰でも使える公開アプリ。仕様の詳細は [`docs/specs/todo-app-spec.md`](docs/specs/todo-app-spec.md) を参照。

## Tech Stack
- FastAPI (Python)
- Jinja2 (サーバーサイドレンダリング。React/Vue等のフロントエンドフレームワークは使わない)
- gspread + サービスアカウント認証(データストア: Google スプレッドシート)
- デプロイ先: Render

## Commands
- `.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8010` — 開発サーバー起動
- `.venv\Scripts\python.exe -m py_compile app/main.py app/sheets.py` — 構文チェック(専用のlintツールは未導入)

## Coding Conventions
- ファイル構成: `app/main.py`(ルーティング) / `app/sheets.py`(Googleスプレッドシート読み書き) / `app/templates/*.html`(Jinja2) / `app/static/`(CSS・素のJS)
- Sheetsのスキーマは**追加専用**。既存列の削除・型変更はしない。新しい列を追加する場合は`app/sheets.py`の`HEADERS`末尾に追加し、既存行でその列が空でも壊れないよう`_normalize()`でデフォルト値を補完する
- 既存シートに新しい列を追加する機能では、隣接列の書式(DATE_TIME等)を引き継いで数値が壊れることがあるため、`_ensure_column_formats()`のように書式を明示的に固定する処理を入れる(詳細は dev-knowledge の `pitfalls/gspread-user-entered-date-format-bleed.md`)
- 依存ライブラリを増やす場合は理由を提示してから追加する(素のJS/CSSで足りる場合はライブラリを増やさない)

## Design Rules
- 配色は青系グラデーション(`app/static/style.css`の`--accent`系変数)で統一。カテゴリ・重要度など意味を持たせた配色を追加する場合も既存のバッジ/グロー/シャドウの表現パターンに合わせる
- ライトモード・ダークモード両方に対応(`@media (prefers-color-scheme: dark)`で変数を上書き)。新しい色を追加する際は両方定義する
- UI品質はグラデーション・グロー・バッジ・シャドウ完備のレベルを維持する(フラットな単色塗りにしない)
- スマホ幅(560px以下)での表示崩れがないか確認する

## Git運用
- 1機能=1コミット。機能追加時は feature branch を切ってから作業し、PRを作ってmainへ取り込む(直接pushしない)
- コミットメッセージは日本語の依頼内容を踏まえて差分から具体的に生成する(「修正」等の曖昧なメッセージにしない)
