# TodoリストWebアプリ 仕様書

*作成日: 2026-07-18*

## 1. 概要
Pythonで作るTodoリスト管理Webアプリ。データはGoogleスプレッドシートに保存し、サーバー(Render)で公開する。

## 2. 機能要件

| 機能 | 内容 |
|------|------|
| 登録 | タイトル・内容・期日を入力してTodoを新規登録 |
| 編集 | 既存Todoのタイトル・内容・期日を編集 |
| 削除 | 一覧から個別に削除 |
| 完了/未完了 | チェックボックスでステータス切り替え。完了は取り消し線+グレー表示 |
| 一覧表示 | 登録済みTodoを一覧確認。期日昇順でソート、期限切れは赤色で強調表示 |
| 認証 | なし(URLを知っていれば誰でも利用可能な公開アプリ) |

## 3. 技術要件

| 項目 | 内容 |
|------|------|
| バックエンド | FastAPI (Python) |
| フロントエンド | Jinja2テンプレート(サーバーサイドレンダリング) |
| データストア | Google スプレッドシート(gspread + サービスアカウント認証) |
| デプロイ先 | Render |
| UI品質レベル | Lv4(グラデーション・グロー・バッジ・シャドウ完備、ダーク/ライト両対応、スマホ表示確認済み) |

## 4. データモデル(スプレッドシート `Todos` シート)

| 列 | 内容 |
|----|------|
| ID | UUID(行の一意識別子) |
| Title | タイトル |
| Content | 内容 |
| DueDate | 期日(YYYY-MM-DD) |
| Status | `pending` / `done` |
| CreatedAt | 作成日時(ISO8601) |
| UpdatedAt | 更新日時(ISO8601) |

## 5. 画面・ルーティング

| パス | メソッド | 内容 |
|------|---------|------|
| `/` | GET | 一覧ページ(期日昇順、期限切れ強調) |
| `/todos/new` | GET | 新規登録フォーム |
| `/todos` | POST | 新規登録処理 |
| `/todos/{id}/edit` | GET | 編集フォーム |
| `/todos/{id}` | POST | 編集更新処理 |
| `/todos/{id}/delete` | POST | 削除処理 |
| `/todos/{id}/toggle` | POST | 完了/未完了切り替え |

## 6. セキュリティ
- サービスアカウントの認証情報はコードに直書きせず、環境変数(`GOOGLE_CREDENTIALS_JSON`)経由で読み込む。
- `.env` は `.gitignore` に追加。
- 本番の環境変数はRenderダッシュボードで管理。

## 7. デプロイ構成
- Render Web Service(Python)
- 起動コマンド: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 環境変数: `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_SHEET_ID`
