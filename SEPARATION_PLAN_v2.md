# TMWS Separation Plan v2.0

## 基本方針
- **Git履歴**: 新規リポジトリでゼロから開始
- **ホスティング**: github.com/apto-as/tmws
- **優先順位**: TMWS分離 → 統合テスト
- **バージョン**: TMWS v1.0.0 / Trinitas v4.0

## インターフェース設計（簡潔版）

### 1. MCP Tools（メイン通信方式）
```yaml
# TMWS が提供するMCPツール
mcp_server: tmws
tools:
  - semantic_search    # メモリ検索
  - store_memory      # メモリ保存
  - manage_task       # タスク管理
  - execute_workflow  # ワークフロー実行
```

### 2. カスタムコマンド
```bash
# /tmws コマンド（システム管理用）
/tmws service status
/tmws db backup
/tmws memory cleanup

# /trinitas コマンド（高レベル操作）
/trinitas execute athena "タスク"
/trinitas remember "キー" "値"
```

### 3. 内部API（外部公開なし）
```yaml
# TMWS内部でFastAPIが動作
# MCPツールがこのAPIを内部的に使用
# 外部からの直接アクセスは不要
```

## 分離手順（シンプル版）

### Phase 1: バックアップ (10分)
```bash
# 1. 現状のバックアップ
cd /Users/apto-as/workspace/github.com/apto-as/
tar -czf trinitas-agents-backup-$(date +%Y%m%d).tar.gz trinitas-agents/

# 2. 作業ブランチ作成
cd trinitas-agents
git checkout -b feature/tmws-separation
git add . && git commit -m "Pre-separation checkpoint"
```

### Phase 2: TMWS抽出 (30分)
```bash
# 1. 新リポジトリ作成
cd /Users/apto-as/workspace/github.com/apto-as/
mkdir tmws
cd tmws
git init

# 2. ファイルコピー
cp -R ../trinitas-agents/tmws/* .
cp ../trinitas-agents/tmws/.env.example .
cp ../trinitas-agents/tmws/.gitignore .

# 3. 初期コミット
git add .
git commit -m "Initial commit: TMWS v1.0.0"

# 4. README作成
cat > README.md << 'EOF'
# TMWS - Trinitas Memory & Workflow Service

Version: 1.0.0

## Overview
Standalone MCP server providing memory management and workflow orchestration for Trinitas AI agents.

## Features
- Semantic memory with PostgreSQL + pgvector
- Task management system
- Workflow orchestration
- MCP protocol support for Claude Desktop

## Quick Start
```bash
./install.sh
python -m src.main
```

## MCP Registration
Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "tmws": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/tmws"
    }
  }
}
```
EOF

git add README.md
git commit -m "Add README"
```

### Phase 3: Trinitas クリーンアップ (20分)
```bash
cd /Users/apto-as/workspace/github.com/apto-as/trinitas-agents/

# 1. TMWSディレクトリ削除
git rm -r tmws/
git commit -m "Remove TMWS (moved to standalone repository)"

# 2. 不要なドキュメント削除
git rm commands/tmws-detailed.md  # 詳細版は削除
git commit -m "Remove TMWS detailed documentation"

# 3. バージョン更新
echo "4.0.0" > VERSION
git add VERSION
git commit -m "Update to v4.0.0 after TMWS separation"
```

### Phase 4: インターフェース調整 (30分)

#### 4.1 MCP設定ファイル作成
```bash
# TMWS側
cd /Users/apto-as/workspace/github.com/apto-as/tmws/

cat > mcp_config.json << 'EOF'
{
  "name": "tmws",
  "version": "1.0.0",
  "description": "Trinitas Memory & Workflow Service",
  "tools": [
    {
      "name": "semantic_search",
      "description": "Search memories using vector similarity",
      "parameters": {
        "query": "string",
        "limit": "number",
        "threshold": "number"
      }
    },
    {
      "name": "store_memory",
      "description": "Store semantic memory",
      "parameters": {
        "content": "string",
        "importance": "number",
        "metadata": "object"
      }
    },
    {
      "name": "manage_task",
      "description": "Manage tasks",
      "parameters": {
        "operation": "string",
        "task_data": "object"
      }
    },
    {
      "name": "execute_workflow",
      "description": "Execute workflow",
      "parameters": {
        "workflow_id": "string",
        "parameters": "object"
      }
    }
  ]
}
EOF
```

#### 4.2 Trinitasコマンド更新
```bash
# Trinitas側
cd /Users/apto-as/workspace/github.com/apto-as/trinitas-agents/

# commands/trinitas.md を更新
# - httpx削除
# - REST API呼び出し削除
# - MCPツール呼び出しのみに簡素化
```

### Phase 5: 統合テスト (30分)

#### 5.1 TMWS起動テスト
```bash
cd /Users/apto-as/workspace/github.com/apto-as/tmws/
python -m src.main  # サーバー起動確認
```

#### 5.2 MCP接続テスト
```python
# テストスクリプト
import asyncio

async def test_mcp_connection():
    # MCPツールの呼び出しテスト
    result = await mcp__tmws__semantic_search(
        query="test",
        limit=5
    )
    print(f"Search result: {result}")
    
    result = await mcp__tmws__store_memory(
        content="Test memory",
        importance=0.5
    )
    print(f"Store result: {result}")

asyncio.run(test_mcp_connection())
```

#### 5.3 コマンドテスト
```bash
# Trinitasコマンドテスト
/trinitas status
/trinitas remember "test" "value"
/trinitas recall "test"

# TMWSコマンドテスト
/tmws health
/tmws memory count
```

## ディレクトリ構造（最終形）

### Trinitas v4.0
```
trinitas-agents/
├── agents/           # AIペルソナ
├── commands/         # カスタムコマンド
│   ├── trinitas.md
│   └── tmws.md      # 簡潔版のみ
├── hooks/           # イベントフック
├── docs/
│   └── tmws-integration.md
└── VERSION          # 4.0.0
```

### TMWS v1.0.0
```
tmws/
├── src/
│   ├── api/         # FastAPI
│   ├── core/        # コア機能
│   ├── models/      # データモデル
│   ├── services/    # ビジネスロジック
│   ├── main.py      # FastAPIサーバー
│   └── mcp_server.py # MCPサーバー
├── tests/
├── migrations/
├── docker/
├── docs/
├── mcp_config.json
├── pyproject.toml
├── README.md
└── VERSION          # 1.0.0
```

## チェックリスト

### 準備
- [ ] バックアップ作成
- [ ] 作業ブランチ作成

### TMWS分離
- [ ] 新リポジトリ作成
- [ ] ファイルコピー
- [ ] README作成
- [ ] 初期コミット

### Trinitas更新
- [ ] TMWSディレクトリ削除
- [ ] 不要ドキュメント削除
- [ ] バージョン更新 (v4.0)

### インターフェース
- [ ] MCP設定作成
- [ ] コマンド更新（httpx削除）

### テスト
- [ ] TMWS起動確認
- [ ] MCP接続確認
- [ ] コマンド動作確認

### 完了
- [ ] GitHub push
- [ ] ドキュメント更新
- [ ] チーム通知

## リスクと対策

| リスク | 対策 |
|--------|------|
| MCP接続失敗 | Claude Desktop設定確認 |
| コマンド動作不良 | MCPツール名の確認 |
| データ損失 | バックアップから復元 |

## 成功基準

1. ✅ TMWSが独立して起動
2. ✅ MCPツール経由で通信可能
3. ✅ カスタムコマンド動作
4. ✅ 機能的な後退なし
5. ✅ クリーンな分離