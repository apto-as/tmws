# TMWS 推奨コマンド

## 開発環境セットアップ
```bash
# 依存関係インストール
pip install -e ".[dev]"

# 環境変数設定
cp .env.example .env
# .envファイルを編集して必要な値を設定
```

## サーバー起動
```bash
# FastAPI サーバー（開発）
uvicorn src.main:app --reload --port 8000

# MCP サーバー
python -m src.mcp_server

# パッケージ版MCP
python -m tmws.mcp_server
```

## データベース
```bash
# マイグレーション作成
alembic revision --autogenerate -m "description"

# マイグレーション実行
alembic upgrade head

# データベース初期化
python scripts/init_db.py
```

## コード品質（現在未設定だが推奨）
```bash
# フォーマット
black src/ tmws/
isort src/ tmws/

# リント
ruff check src/ tmws/
mypy src/ tmws/

# テスト（未実装）
pytest tests/ -v --cov=src
```

## セキュリティ
```bash
# セキュリティセットアップ
python scripts/security_setup.py

# 環境変数確認
env | grep TMWS_
```

## Git
```bash
# ステータス確認
git status

# 変更内容確認
git diff

# コミット履歴
git log --oneline -n 10
```