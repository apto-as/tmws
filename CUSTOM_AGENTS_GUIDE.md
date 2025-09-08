# TMWS カスタムエージェント登録ガイド

## 概要

TMWS v3.1では、デフォルトの6つのTrinitasエージェントに加えて、カスタムエージェントを動的に登録・管理できるようになりました。

## デフォルトエージェント（Trinitas）

以下の6つのシステムエージェントは常に利用可能です：

1. **Athena** (`athena-conductor`) - システム全体の調和的な指揮
2. **Artemis** (`artemis-optimizer`) - パフォーマンス最適化と技術的卓越性
3. **Hestia** (`hestia-auditor`) - セキュリティ分析と監査
4. **Eris** (`eris-coordinator`) - 戦術計画とチーム調整
5. **Hera** (`hera-strategist`) - 戦略計画とアーキテクチャ設計
6. **Muses** (`muses-documenter`) - ドキュメント作成と知識管理

## カスタムエージェントの登録

### 1. MCPツールによる登録

```python
# Claudeから直接登録
await mcp_client.call_tool("register_agent", {
    "agent_name": "researcher",
    "full_id": "research-specialist",
    "capabilities": [
        "literature_review",
        "data_analysis",
        "hypothesis_generation"
    ],
    "namespace": "academic",
    "display_name": "Research Specialist",
    "access_level": "team",
    "metadata": {
        "specialization": "AI/ML Research",
        "languages": ["English", "Japanese"]
    }
})
```

### 2. 設定ファイルによる登録

`custom_agents.json`を作成：

```json
{
  "version": "1.0",
  "custom_agents": [
    {
      "name": "researcher",
      "full_id": "research-specialist",
      "namespace": "academic",
      "display_name": "Research Specialist",
      "access_level": "team",
      "capabilities": [
        "literature_review",
        "data_analysis",
        "hypothesis_generation"
      ],
      "metadata": {
        "specialization": "AI/ML Research"
      }
    }
  ]
}
```

起動時に自動的に読み込まれる設定ファイルの場所：
- `./custom_agents.json` （カレントディレクトリ）
- `~/.tmws/custom_agents.json` （ユーザーホーム）
- `/etc/tmws/custom_agents.json` （システム全体）

### 3. 環境変数による初期エージェント設定

```bash
# デフォルトエージェントを設定
export TMWS_AGENT_ID="researcher"
export TMWS_AGENT_NAMESPACE="academic"
export TMWS_AGENT_CAPABILITIES='{"research": true, "analysis": true}'
```

## パラメータ説明

### 必須パラメータ

- **agent_name**: エージェントの短縮名（2-32文字、英字で開始、英数字・ハイフン・アンダースコア）
- **full_id**: 完全な識別子（3-64文字）
- **capabilities**: エージェントの能力リスト

### オプションパラメータ

- **namespace**: 名前空間（デフォルト: "custom"）
- **display_name**: 表示名（人間が読みやすい名前）
- **access_level**: アクセスレベル
  - `private`: エージェント自身のみ
  - `team`: 同じnamespace内で共有
  - `shared`: 明示的に共有されたエージェント
  - `public`: すべてのエージェントからアクセス可能
- **metadata**: 追加メタデータ（JSON形式）

## エージェント管理操作

### エージェントの切り替え

```python
# カスタムエージェントに切り替え
await mcp_client.call_tool("switch_agent", {"agent_name": "researcher"})

# Trinitasエージェントに戻す
await mcp_client.call_tool("switch_agent", {"agent_name": "athena"})
```

### エージェントの一覧表示

```python
# すべての利用可能なエージェントを表示
result = await mcp_client.call_tool("list_trinitas_agents", {})
# Trinitas 6個 + カスタムエージェントが表示される
```

### 一時的なエージェント実行

```python
# 現在のエージェントを変更せずに、特定のエージェントとして実行
await mcp_client.call_tool("execute_as_agent", {
    "agent_name": "researcher",
    "action": "create_memory",
    "parameters": {
        "content": "Research finding: ...",
        "importance": 0.9
    }
})
```

### エージェントの削除

```python
# カスタムエージェントを削除（Trinitasエージェントは削除不可）
await mcp_client.call_tool("unregister_agent", {"agent_name": "researcher"})
```

### プロファイルの保存と読み込み

```python
# 現在のカスタムエージェントを保存
await mcp_client.call_tool("save_agent_profiles", {
    "filepath": "my_agents.json"
})

# プロファイルから読み込み
await mcp_client.call_tool("load_agent_profiles", {
    "filepath": "my_agents.json"
})
```

## 使用例

### 例1: プロジェクト固有のエージェントチーム

```json
{
  "custom_agents": [
    {
      "name": "frontend",
      "full_id": "frontend-developer",
      "capabilities": ["react", "typescript", "ui_development"],
      "namespace": "development"
    },
    {
      "name": "backend",
      "full_id": "backend-developer",
      "capabilities": ["python", "fastapi", "database_design"],
      "namespace": "development"
    },
    {
      "name": "qa",
      "full_id": "qa-engineer",
      "capabilities": ["testing", "automation", "bug_tracking"],
      "namespace": "development"
    }
  ]
}
```

### 例2: 多言語サポートエージェント

```python
await mcp_client.call_tool("register_agent", {
    "agent_name": "translator_ja",
    "full_id": "japanese-translator",
    "capabilities": ["translation", "localization", "cultural_adaptation"],
    "namespace": "language",
    "display_name": "日本語翻訳スペシャリスト",
    "metadata": {
        "source_languages": ["English", "Chinese"],
        "target_language": "Japanese",
        "specialties": ["Technical", "Business"]
    }
})
```

### 例3: ドメイン専門家エージェント

```python
# 医療専門エージェント
await mcp_client.call_tool("register_agent", {
    "agent_name": "medical",
    "full_id": "medical-expert",
    "capabilities": [
        "medical_terminology",
        "diagnosis_support",
        "treatment_planning",
        "medical_research"
    ],
    "namespace": "healthcare",
    "access_level": "private",  # プライバシー保護のため
    "metadata": {
        "certifications": ["MD", "PhD"],
        "specializations": ["Internal Medicine", "Cardiology"]
    }
})
```

## セキュリティ考慮事項

1. **名前の衝突防止**: Trinitasエージェント名は予約されており、上書きできません
2. **バリデーション**: エージェント名とIDは厳格な形式チェックを受けます
3. **アクセス制御**: `access_level`により、メモリへのアクセスを制御
4. **監査ログ**: すべてのエージェント切り替えは履歴に記録されます

## トラブルシューティング

### エラー: "Name conflicts with system agent"
Trinitasエージェント（athena, artemis, hestia, eris, hera, muses）の名前は使用できません。

### エラー: "Invalid agent name"
エージェント名は英字で始まり、2-32文字である必要があります。

### エラー: "Agent is already registered"
同じ名前のエージェントが既に存在します。`unregister_agent`で削除してから再登録してください。

## まとめ

カスタムエージェント機能により、TMWSは真に汎用的なマルチエージェント記憶管理システムとなりました。プロジェクトやチームのニーズに応じて、任意のAIエージェントを定義し、それぞれが独立した記憶とコンテキストを持ちながら協調作業を行うことができます。