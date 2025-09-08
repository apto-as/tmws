# TMWS エージェント切り替え設計

## 結論：ハイブリッドアプローチ（方法3の拡張）

Trinitasエージェント全員の協議により、以下の実装を推奨します。

## 実装方針

### 1. 基本構造
```python
class AgentContextManager:
    """エージェントコンテキスト管理"""
    
    # 事前定義されたTrinitasエージェント
    TRINITAS_AGENTS = {
        "athena": {
            "full_id": "athena-conductor",
            "namespace": "trinitas",
            "capabilities": ["orchestration", "workflow_automation"],
            "access_level": "system"
        },
        "artemis": {
            "full_id": "artemis-optimizer",
            "namespace": "trinitas",
            "capabilities": ["performance_optimization", "code_quality"],
            "access_level": "team"
        },
        "hestia": {
            "full_id": "hestia-auditor",
            "namespace": "trinitas",
            "capabilities": ["security_analysis", "audit_logging"],
            "access_level": "system",
            "special_permissions": ["audit_all"]
        },
        "eris": {
            "full_id": "eris-coordinator",
            "namespace": "trinitas",
            "capabilities": ["tactical_planning", "team_coordination"],
            "access_level": "team"
        },
        "hera": {
            "full_id": "hera-strategist",
            "namespace": "trinitas",
            "capabilities": ["strategic_planning", "architecture_design"],
            "access_level": "team"
        },
        "muses": {
            "full_id": "muses-documenter",
            "namespace": "trinitas",
            "capabilities": ["documentation", "knowledge_management"],
            "access_level": "public"
        }
    }
    
    def __init__(self):
        # デフォルトは環境変数から
        self.default_agent = os.getenv("TMWS_AGENT_ID", "athena-conductor")
        self.current_agent = self.default_agent
        self.agent_history = []
```

### 2. MCPツール実装

```python
@mcp.tool()
async def switch_agent(agent_name: str) -> Dict[str, Any]:
    """
    エージェントを切り替える
    
    Args:
        agent_name: "athena", "artemis", "hestia", "eris", "hera", "muses"
    
    Returns:
        切り替え結果
    """
    if agent_name not in AgentContextManager.TRINITAS_AGENTS:
        return {
            "success": False,
            "error": f"Unknown agent: {agent_name}",
            "available_agents": list(AgentContextManager.TRINITAS_AGENTS.keys())
        }
    
    agent_info = AgentContextManager.TRINITAS_AGENTS[agent_name]
    
    # コンテキストを更新
    context.agent_history.append(context.current_agent)
    context.current_agent = agent_info["full_id"]
    context.namespace = agent_info["namespace"]
    context.capabilities = agent_info["capabilities"]
    
    return {
        "success": True,
        "current_agent": agent_name,
        "full_id": agent_info["full_id"],
        "capabilities": agent_info["capabilities"],
        "access_level": agent_info["access_level"]
    }


@mcp.tool()
async def get_current_agent() -> Dict[str, Any]:
    """現在のエージェント情報を取得"""
    return {
        "current_agent": context.current_agent,
        "namespace": context.namespace,
        "capabilities": context.capabilities,
        "history": context.agent_history[-5:]  # 直近5件の履歴
    }


@mcp.tool()
async def execute_as_agent(
    agent_name: str,
    action: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    特定のエージェントとしてアクションを実行
    
    Args:
        agent_name: エージェント名
        action: 実行するアクション
        parameters: アクションのパラメータ
    
    Example:
        execute_as_agent("hestia", "security_audit", {"target": "system"})
    """
    # 現在のエージェントを保存
    original_agent = context.current_agent
    
    try:
        # エージェントを切り替え
        await switch_agent(agent_name)
        
        # アクションを実行
        if action == "create_memory":
            result = await create_memory(**parameters)
        elif action == "search_memories":
            result = await search_memories(**parameters)
        elif action == "security_audit":
            result = await perform_security_audit(**parameters)
        # ... 他のアクション
        else:
            result = {"error": f"Unknown action: {action}"}
        
        return {
            "executed_as": agent_name,
            "action": action,
            "result": result
        }
        
    finally:
        # 元のエージェントに戻す
        context.current_agent = original_agent
```

### 3. メモリ操作の拡張

```python
@mcp.tool()
async def create_memory(
    content: str,
    tags: List[str] = None,
    importance: float = 0.5,
    as_agent: Optional[str] = None,  # 一時的にエージェントを指定
    share_with: List[str] = None     # 共有するエージェント
) -> Dict[str, Any]:
    """
    メモリを作成（エージェント指定可能）
    
    Args:
        content: メモリ内容
        as_agent: このメモリを作成するエージェント（省略時は現在のエージェント）
        share_with: 共有するエージェントのリスト
    """
    # エージェントの決定
    if as_agent:
        agent_info = AgentContextManager.TRINITAS_AGENTS.get(as_agent)
        if not agent_info:
            return {"error": f"Unknown agent: {as_agent}"}
        agent_id = agent_info["full_id"]
    else:
        agent_id = context.current_agent
    
    # メモリ作成
    memory = await context.memory_service.create_memory(
        content=content,
        agent_id=agent_id,
        namespace=context.namespace,
        tags=tags or [],
        importance_score=importance,
        shared_with_agents=share_with
    )
    
    return {
        "success": True,
        "memory_id": str(memory.id),
        "created_by": agent_id,
        "shared_with": share_with or []
    }
```

### 4. セキュリティ考慮事項

```python
class AgentPermissionChecker:
    """エージェント権限チェック"""
    
    PERMISSION_MATRIX = {
        "athena": {
            "can_switch_to": ["all"],
            "can_access_memories_of": ["all"],
            "can_delete": True,
            "can_audit": True
        },
        "hestia": {
            "can_switch_to": ["all"],
            "can_access_memories_of": ["all"],
            "can_delete": False,
            "can_audit": True
        },
        "artemis": {
            "can_switch_to": ["artemis", "eris"],
            "can_access_memories_of": ["team"],
            "can_delete": False,
            "can_audit": False
        },
        # ... 他のエージェント
    }
    
    @staticmethod
    def can_switch(from_agent: str, to_agent: str) -> bool:
        """エージェント切り替え権限をチェック"""
        permissions = AgentPermissionChecker.PERMISSION_MATRIX.get(from_agent, {})
        allowed = permissions.get("can_switch_to", [])
        return "all" in allowed or to_agent in allowed
```

## 利点

1. **柔軟性**: 実行時にエージェントを切り替え可能
2. **互換性**: 環境変数ベースの既存実装と共存
3. **セキュリティ**: 権限マトリックスによる制御
4. **トレーサビリティ**: エージェント切り替え履歴を記録
5. **拡張性**: 新しいエージェントの追加が容易

## 実装優先順位

### Phase 1（即座に実装）
- `switch_agent` ツール
- `get_current_agent` ツール
- 基本的なコンテキスト管理

### Phase 2（1週間以内）
- `execute_as_agent` ツール
- メモリ操作への `as_agent` パラメータ追加
- エージェント履歴管理

### Phase 3（2週間以内）
- 権限マトリックス実装
- セキュリティ監査ログ
- パフォーマンス最適化

## 使用例

```python
# Claudeでの使用例
await mcp_client.call_tool("switch_agent", {"agent_name": "athena"})
await mcp_client.call_tool("create_memory", {
    "content": "System architecture overview",
    "share_with": ["artemis", "hera"]
})

# Artemisとして最適化分析を実行
await mcp_client.call_tool("execute_as_agent", {
    "agent_name": "artemis",
    "action": "analyze_performance",
    "parameters": {"target": "database_queries"}
})

# Hestiaとしてセキュリティ監査
await mcp_client.call_tool("execute_as_agent", {
    "agent_name": "hestia",
    "action": "security_audit",
    "parameters": {"scope": "full_system"}
})
```

## 結論

このハイブリッドアプローチにより：
- 環境変数による初期設定を維持
- MCPツールで動的にエージェントを切り替え
- Trinitasの6エージェントを事前定義
- 将来的な拡張にも対応可能

これが最も実用的かつ柔軟な解決策です。