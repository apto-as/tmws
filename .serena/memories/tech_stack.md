# TMWS 技術スタック

## コアフレームワーク
- **FastAPI** (>=0.104.0): REST API フレームワーク
- **FastMCP** (>=0.1.0): Model Context Protocol サーバー
- **MCP** (>=0.9.0): Claude統合プロトコル

## データベース
- **PostgreSQL**: メインデータベース
- **pgvector** (>=0.2.4): ベクトル検索拡張（384次元）
- **SQLAlchemy** (>=2.0.23): 非同期ORM
- **asyncpg** (>=0.29.0): 非同期PostgreSQLドライバー
- **Alembic** (>=1.12.0): データベースマイグレーション

## AI/ML
- **sentence-transformers** (>=2.2.0): all-MiniLM-L6-v2 モデル
- **numpy** (>=1.24.0): 数値計算

## 非同期処理
- **uvicorn[standard]** (>=0.24.0): ASGI サーバー
- **uvloop**: 高性能イベントループ
- **aiohttp** (>=3.9.0): 非同期HTTPクライアント

## データ検証
- **Pydantic** (>=2.4.0): データ検証とシリアライゼーション
- **pydantic-settings** (>=2.0.0): 設定管理

## セキュリティ
- **python-jose[cryptography]** (>=3.3.0): JWT実装
- **passlib[bcrypt]** (>=1.7.4): パスワードハッシュ
- **cryptography** (>=41.0.0): 暗号化

## バックグラウンドタスク
- **Celery** (>=5.3.0): タスクキュー
- **Redis** (>=5.0.0): キャッシュ/メッセージブローカー

## 開発ツール（未実装）
- **pytest**: テストフレームワーク
- **black**: コードフォーマッター
- **ruff**: リンター
- **mypy**: 型チェッカー