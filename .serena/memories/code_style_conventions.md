# TMWS コーディング規約

## Python スタイル
- **Pythonバージョン**: 3.10+
- **行長**: 100文字
- **インデント**: スペース4つ
- **フォーマッター**: Black（設定済み、未実行）
- **インポート順**: isort profile="black"

## 型ヒント
- **使用率**: 97%（ほぼ全て型ヒント付き）
- **厳密さ**: mypy strict設定
- **Pydantic**: BaseModel継承で自動検証

## 非同期パターン
- **全て非同期**: async/await を全面採用
- **データベース**: asyncpg + SQLAlchemy async
- **イベントループ**: uvloop

## 命名規則
- **クラス**: PascalCase (例: `MemoryService`)
- **関数/メソッド**: snake_case (例: `create_memory`)
- **定数**: UPPER_SNAKE_CASE (例: `MAX_RETRIES`)
- **プライベート**: アンダースコア接頭辞 (例: `_internal_method`)

## ファイル構造
- **モデル**: `models/` ディレクトリ
- **サービス**: `services/` ディレクトリ（ビジネスロジック）
- **API**: `api/` ディレクトリ（エンドポイント）
- **ツール**: `tools/` ディレクトリ（MCP実装）

## エラーハンドリング
- **基底クラス**: `TMWSException`
- **階層的例外**: 用途別に継承
- **ログ**: structlog使用

## ドキュメント
- **Docstring**: Google スタイル推奨（現在は最小限）
- **型ヒント**: 必須
- **コメント**: 最小限、コードで意図を表現