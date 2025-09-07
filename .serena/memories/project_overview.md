# TMWS - Trinitas Memory & Workflow Service

## プロジェクト概要
- **バージョン**: 1.0.0
- **目的**: Trinitas AIエージェント向けのメモリ管理とワークフローオーケストレーション
- **アーキテクチャ**: FastAPI + FastMCP による双方向プロトコル対応

## 主要機能
1. **セマンティックメモリ管理**: PostgreSQL + pgvector によるベクトル検索
2. **タスク管理システム**: 優先度とステータス管理
3. **ワークフローオーケストレーション**: 並列処理と依存関係管理
4. **ペルソナ管理**: 6つのAIペルソナ（Athena, Artemis, Hestia, Eris, Hera, Muses）
5. **学習パターンシステム**: パターン認識と自動最適化
6. **セキュリティ**: レート制限、監査ログ、入力検証

## ディレクトリ構造
- `src/` と `tmws/`: 同一実装の重複（開発用とパッケージ配布用）
- `core/`: 基幹システム（config, database, exceptions）
- `api/`: FastAPI ルーターとミドルウェア
- `services/`: ビジネスロジック層
- `models/`: SQLAlchemy データモデル
- `tools/`: MCP ツール実装
- `security/`: セキュリティモジュール
- `integration/`: FastAPI-MCP ブリッジ