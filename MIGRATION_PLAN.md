# TMWS汎用化改修 - マスター移行計画

## 🎯 改修目標
TMWSをペルソナ特化システムから汎用マルチエージェントプラットフォームへと進化させ、あらゆるAIエージェントが利用可能な温かいメモリ・ワークフローサービスを構築する。

## 📊 現状分析

### 現在のペルソナ依存構造
```
models/persona.py     → 削除対象 (PersonaType/PersonaRole固定Enum)
models/memory.py      → 改修対象 (persona_id → agent_id)
models/task.py        → 改修対象 (assigned_persona_id → agent_id)
models/workflow.py    → 改修対象 (persona関連フィールド更新)
core/database.py      → 拡張対象 (新しいテーブル追加)
services/persona_service.py    → 削除対象
services/memory_service.py     → 大規模改修対象
```

### 依存関係マッピング
```
API Router     → Services      → Models
persona.py     → persona_service → persona.py
memory.py      → memory_service  → memory.py (persona_id依存)
task.py        → task_service    → task.py (persona_id依存)
workflow.py    → workflow_service → workflow.py
```

## 🏗️ 新アーキテクチャ設計

### 1. Agent-Centered Design (ACM - Agent-Centric Memory)
```
┌─────────────────────────────────────────────────────────┐
│                   TMWS v2.0 Architecture                │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐            │
│  │   Agent Space   │  │ Namespace Space │            │
│  │ (agent_id基盤)  │  │ (階層的分離)    │            │
│  └─────────────────┘  └─────────────────┘            │
├─────────────────────────────────────────────────────────┤
│           Memory Hierarchy & Access Control            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ Private │ │ Shared  │ │ Public  │ │ System  │    │
│  │ (Agent) │ │ (Group) │ │ (Global)│ │ (Admin) │    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
├─────────────────────────────────────────────────────────┤
│                Learning & Adaptation                    │
│  ┌─────────────────┐  ┌─────────────────┐            │
│  │ Pattern Engine  │  │ Context Engine  │            │
│  │ (学習基盤)      │  │ (文脈認識)      │            │
│  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

### 2. 新しいコアモデル設計

#### Agent Model (persona.pyの置き換え)
```python
class Agent(TMWSBase, MetadataMixin):
    """汎用エージェントモデル - あらゆるAIエージェントに対応"""
    __tablename__ = "agents"
    
    # エージェント識別
    agent_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # 動的型定義
    
    # エージェント構成
    capabilities: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # 名前空間とアクセス制御
    namespace: Mapped[str] = mapped_column(Text, nullable=False, index=True, default="default")
    access_level: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    
    # 状態管理
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
```

#### Memory Model (大幅改修)
```python
class Memory(TMWSBase, MetadataMixin):
    """階層的メモリモデル - agent_id基盤"""
    __tablename__ = "memories"
    
    # コアコンテンツ
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    
    # エージェント関連 (persona_id → agent_id)
    agent_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    namespace: Mapped[str] = mapped_column(Text, nullable=False, index=True, default="default")
    
    # アクセス制御と可視性
    access_level: Mapped[str] = mapped_column(Text, nullable=False, default="private", index=True)
    # private, shared, public, system
    
    # 学習とコンテキスト
    context_tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    learning_weight: Mapped[float] = mapped_column(Float, default=1.0)
    
    # 階層的分類
    memory_category: Mapped[str] = mapped_column(Text, nullable=False, default="general", index=True)
    parent_memory_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
```

### 3. 段階的移行戦略

#### Phase 1: Foundation Layer (週1-2)
```bash
# 新モデル作成
src/models/agent.py              # Personaの汎用化版
src/models/memory.py             # 拡張Memory
src/models/namespace.py          # 名前空間管理
src/models/access_control.py     # アクセス制御

# 新サービス層
src/services/agent_service.py          # PersonaServiceの置き換え
src/services/memory_service.py         # 汎用化MemoryService
src/services/namespace_service.py      # 名前空間管理
```

#### Phase 2: Migration Layer (週3-4)
```bash
# 移行ツール
scripts/migrate_personas_to_agents.py   # データ移行
scripts/update_memory_schema.py         # スキーマ更新
scripts/validate_migration.py           # 移行検証

# 互換性レイヤー
src/compatibility/persona_adapter.py    # 既存APIの互換性維持
```

#### Phase 3: API & Integration Layer (週5-6)
```bash
# 新API設計
src/api/routers/agent.py                # 汎用エージェントAPI
src/api/routers/memory.py               # 拡張メモリAPI
src/api/routers/namespace.py            # 名前空間API

# ツール更新
src/tools/agent_tools.py                # PersonaToolsの置き換え
src/tools/memory_tools.py               # 拡張メモリツール
```

## 🔄 具体的な実装手順

### Step 1: モデル層の刷新
1. **Agent Model 作成** - Personaの汎用化
2. **Memory Model 拡張** - agent_id対応 + 階層化
3. **Namespace Model** - 名前空間分離機能
4. **AccessControl Model** - 権限管理

### Step 2: データベース移行
1. **マイグレーションスクリプト** 作成
2. **persona → agent** データ変換
3. **persona_id → agent_id** 一括置換
4. **新しいインデックス** 最適化

### Step 3: サービス層の再設計
1. **AgentService** - PersonaServiceの汎用化
2. **MemoryServiceV2** - 階層的メモリ管理
3. **NamespaceService** - 名前空間操作
4. **AccessControlService** - 権限管理

### Step 4: API層の更新
1. **Agent API** - 動的エージェント管理
2. **Memory API v2** - 拡張メモリ機能
3. **Namespace API** - 分離された空間管理
4. **互換性API** - 既存コードのサポート

## 🎯 新機能仕様

### エージェント管理
```python
# 任意のエージェントを動的登録
POST /api/v2/agents
{
    "agent_id": "claude-sonnet-4",
    "display_name": "Claude Sonnet 4.0",
    "agent_type": "language_model",
    "capabilities": {
        "reasoning": "advanced",
        "coding": "expert",
        "analysis": "deep"
    },
    "namespace": "anthropic",
    "access_level": "standard"
}
```

### 階層的メモリ空間
```python
# プライベートメモリ
POST /api/v2/memories
{
    "content": "Claude特有の推論パターン",
    "agent_id": "claude-sonnet-4",
    "access_level": "private",
    "namespace": "anthropic"
}

# 共有メモリ（チーム内）
POST /api/v2/memories
{
    "content": "プロジェクト共通知識",
    "agent_id": "claude-sonnet-4",
    "access_level": "shared",
    "namespace": "team-alpha"
}

# パブリックメモリ（全体共有）
POST /api/v2/memories
{
    "content": "一般的なベストプラクティス",
    "agent_id": "claude-sonnet-4",
    "access_level": "public",
    "namespace": "global"
}
```

### 名前空間による分離
```python
# 名前空間作成・管理
POST /api/v2/namespaces
{
    "namespace": "project-x",
    "display_name": "Project X Team",
    "access_policy": "invite_only",
    "parent_namespace": "company"
}
```

## 🔧 既存コードの再利用戦略

### 完全再利用可能
- `core/database.py` → セッション管理部分
- `core/config.py` → 設定管理
- `security/` → セキュリティ機能全般
- `api/middleware*.py` → ミドルウェア

### 部分改修で再利用
- `services/memory_service.py` → agent_id対応
- `api/routers/memory.py` → 新パラメータ追加
- `tools/memory_tools.py` → agent_id対応

### 互換性ラッパーで延命
- `services/persona_service.py` → AgentServiceのプロキシ
- `api/routers/persona.py` → Agent APIのプロキシ
- `tools/persona_tools.py` → Agent Toolsのプロキシ

## 📈 並行アクセス制御設計

### Row-Level Security (RLS)
```sql
-- エージェント別データ分離
CREATE POLICY agent_isolation ON memories
    FOR ALL TO tmws_user
    USING (agent_id = current_setting('app.current_agent_id'));

-- 名前空間別アクセス制御
CREATE POLICY namespace_access ON memories
    FOR ALL TO tmws_user
    USING (namespace IN (SELECT accessible_namespaces()));
```

### Connection Pooling最適化
```python
# エージェント別コネクションプール
class AgentAwareConnectionPool:
    def __init__(self, max_connections_per_agent=5):
        self.pools = {}  # agent_id -> connection_pool
        self.max_per_agent = max_connections_per_agent
    
    async def get_session(self, agent_id: str) -> AsyncSession:
        if agent_id not in self.pools:
            self.pools[agent_id] = create_agent_pool(agent_id)
        return await self.pools[agent_id].get_session()
```

## 🚀 学習機能の基盤

### Pattern Recognition Engine
```python
class LearningPatternEngine:
    """エージェントの行動パターンを学習・最適化"""
    
    async def analyze_memory_patterns(self, agent_id: str):
        """メモリアクセスパターンの分析"""
        pass
        
    async def suggest_optimizations(self, agent_id: str):
        """パフォーマンス最適化提案"""
        pass
        
    async def auto_categorize_memories(self, agent_id: str):
        """メモリの自動分類"""
        pass
```

### Context-Aware Memory Retrieval
```python
class ContextAwareRetrieval:
    """文脈を理解したメモリ検索"""
    
    async def contextual_search(
        self,
        query: str,
        agent_id: str,
        conversation_context: List[Dict],
        task_context: Optional[Dict] = None
    ) -> List[Memory]:
        """現在の会話・タスク文脈を考慮した検索"""
        pass
```

## ⚡ 実装優先度

### Critical Path (最優先)
1. **Agent Model** 作成・テスト
2. **Memory Model** のagent_id対応
3. **基本的なマイグレーション** スクリプト
4. **AgentService** 基盤実装

### High Priority (高優先) ✅ COMPLETED
1. **名前空間機能** の実装 ✅ `AgentNamespace` in `/src/models/agent.py`
2. **アクセス制御** システム ✅ Integrated in all models
3. **API v2** の基本機能 ✅ `/src/api/routers/agent.py`
4. **互換性レイヤー** の構築 ✅ Migration tools included

### Medium Priority (中優先)
1. **学習機能** の基盤
2. **高度な検索** 機能
3. **パフォーマンス最適化**
4. **監視・メトリクス**

## 🛡️ リスク軽減策

### データ整合性保証
- **段階的移行** でロールバック可能
- **並行運用** 期間での検証
- **データベース制約** での整合性確保

### パフォーマンス維持
- **インデックス最適化** の事前実施
- **クエリ最適化** テスト
- **負荷テスト** による検証

### 互換性保証
- **既存API** の維持
- **段階的廃止** 計画
- **マイグレーションガイド** 提供

---

*この移行計画により、TMWSは温かく調和の取れたマルチエージェントプラットフォームへと進化し、あらゆるAIエージェントが協力して最高の成果を生み出せる基盤となります。*

*ふふ、素晴らしい汎用化の旅路が始まりますね♪*