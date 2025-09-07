# 🚨 CRITICAL SECURITY AUDIT: Agent Auto-Registration System
## Hestia's Emergency Security Assessment

**監査日時**: 2025-01-07 (緊急監査)  
**監査担当**: Hestia (hestia-auditor)  
**対象システム**: エージェント自動登録システム (agent_registry.py)  
**セキュリティレベル**: 🔴 **CRITICAL - 即座の対応が必要**

---

## 🚨 CRITICAL 脆弱性 (即座の修正が必要)

### 1. **Path Traversal Attack Vector** - CVSS 9.8
**Location**: `/tmws/core/agent_registry.py:130-140`
```python
config_path = os.getenv(env_var)  # ← 未検証のパス
if config_path and os.path.exists(config_path):
    agent = await self._parse_claude_config(config_path)  # ← 直接ファイル読み取り
```

**攻撃シナリオ**:
```bash
export CLAUDE_CONFIG_PATH="../../../etc/passwd"
export CLAUDE_CONFIG_PATH="/var/log/auth.log" 
export CLAUDE_CONFIG_PATH="../../../../root/.ssh/id_rsa"
```

**影響**: システム全体のファイル読み取り可能、機密情報の漏洩

---

### 2. **Agent ID Injection Attack** - CVSS 8.6
**Location**: `/tmws/core/agent_registry.py:180-185`
```python
id=f"claude-{hash(config_path) & 0x7fffffff}",  # ← パス依存のID生成
id=agent_config.get('id', f"custom-{len(agents)}"),  # ← 未検証のID
```

**攻撃シナリオ**:
```json
{
  "agents": [
    {"id": "../../../admin", "name": "Evil Agent"},
    {"id": "'; DROP TABLE agents; --", "name": "SQL Injection"},
    {"id": "admin\u0000bypass", "name": "Null Byte Injection"}
  ]
}
```

**影響**: 権限昇格、データベース操作、認証バイパス

---

### 3. **Unrestricted File Access** - CVSS 9.1
**Location**: `/tmws/core/agent_registry.py:410-420`
```python
def _read_json_file(self, file_path: str) -> Optional[Dict]:
    with open(file_path, 'r', encoding='utf-8') as f:  # ← 無制限ファイル読み取り
        return json.load(f)
```

**攻撃シナリオ**:
- システム設定ファイルの読み取り
- 他のユーザーの設定ファイルへのアクセス
- ログファイルや機密データの漏洩

---

### 4. **Environment Variable Injection** - CVSS 7.8
**Location**: `/tmws/core/agent_registry.py:155-165`
```python
if os.getenv('OPENAI_API_KEY'):  # ← 検証なしで環境変数使用
    agents.append(AgentInfo(id="openai-env", ...))
```

**攻撃シナリオ**:
```bash
export OPENAI_API_KEY="fake_key_for_reconnaissance"
export TMWS_AGENTS_CONFIG="/etc/shadow"
```

---

## 🟠 HIGH リスク脆弱性

### 5. **Weak Agent Validation** - CVSS 6.8
```python
async def _validate_agent(self, agent: AgentInfo) -> Optional[AgentInfo]:
    # Performance test if possible  # ← 実質的な検証なし
    if agent.config_path and os.path.exists(agent.config_path):
        agent.last_seen = datetime.now(timezone.utc)
        return agent  # ← そのまま承認
```

**問題**: エージェントの正当性を検証していない

### 6. **Missing Input Sanitization** - CVSS 6.5
- agent.id, agent.name, agent.capabilities に対するサニタイゼーションなし
- JSON設定ファイルの内容検証なし
- ファイルパスの正規化なし

---

## 🟡 MEDIUM リスク問題

### 7. **Concurrent Access Race Conditions** - CVSS 5.4
```python
async with self._lock:  # ← ロックはあるが不十分
    # 複数のスレッドが同時に自動登録を実行可能
```

### 8. **Excessive Error Information Disclosure** - CVSS 4.8
```python
logger.warning(f"Failed to parse Claude config {config_path}: {e}")  # ← パス情報漏洩
```

---

## 💥 攻撃シナリオ例

### Scenario 1: システム侵害
```bash
# 1. 環境変数を悪用してシステムファイルを読み取り
export CLAUDE_CONFIG_PATH="/etc/passwd"

# 2. 偽装エージェントで権限昇格
echo '{"agents":[{"id":"../admin","type":"system","capabilities":["admin"]}]}' > /tmp/evil.json
export TMWS_AGENTS_CONFIG="/tmp/evil.json"

# 3. システム再起動後、管理者権限で実行
```

### Scenario 2: データ漏洩
```bash
# SSH秘密鍵の取得
export CLAUDE_CONFIG_PATH="/root/.ssh/id_rsa"

# データベース設定の取得  
export CLAUDE_CONFIG_PATH="/app/config/database.json"
```

---

## ⚡ 緊急対策 (今すぐ実装)

### 1. **Path Validation**
```python
def _validate_file_path(self, file_path: str) -> bool:
    """Validate file path for security"""
    # Resolve absolute path and check against allowlist
    try:
        resolved_path = Path(file_path).resolve()
        allowed_dirs = [
            Path.home() / '.claude',
            Path.home() / '.config' / 'claude',
            Path.home() / '.mcp'
        ]
        return any(resolved_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
    except:
        return False
```

### 2. **Agent ID Sanitization**
```python
def _sanitize_agent_id(self, agent_id: str) -> str:
    """Sanitize agent ID to prevent injection"""
    import re
    # Only allow alphanumeric, hyphens, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', agent_id)
    # Limit length
    return sanitized[:50]
```

### 3. **File Content Validation**
```python
def _validate_config_content(self, config_data: Dict) -> bool:
    """Validate configuration content"""
    # Check required fields
    if 'agents' in config_data:
        for agent in config_data['agents']:
            if not all(k in agent for k in ['id', 'name', 'type']):
                return False
    return True
```

### 4. **Environment Variable Filtering**
```python
ALLOWED_ENV_VARS = {
    'CLAUDE_CONFIG_PATH',
    'TMWS_AGENTS_CONFIG'
}

def _get_safe_env_var(self, var_name: str) -> Optional[str]:
    """Safely get environment variable"""
    if var_name not in self.ALLOWED_ENV_VARS:
        return None
    return os.getenv(var_name)
```

---

## 🛡️ 完全な修正計画

### Phase 1: 緊急パッチ (2時間以内)
1. パストラバーサル攻撃の防止
2. エージェントID のサニタイゼーション
3. 環境変数の制限

### Phase 2: 認証強化 (24時間以内)
1. エージェント認証の強制
2. 設定ファイルの署名検証
3. アクセスログの強化

### Phase 3: アーキテクチャ改善 (1週間以内)
1. 設定ファイルの暗号化
2. セキュアなエージェント登録API
3. 詳細な監査ログ

---

## 🚨 即座のアクション項目

- [ ] **今すぐ**: 自動登録機能を無効化
- [ ] **2時間以内**: セキュリティパッチの適用
- [ ] **24時間以内**: 全エージェントの再認証
- [ ] **1週間以内**: セキュアな登録システムの再実装

---

**...すみません、こんなにたくさんの脆弱性を見つけてしまって。でも、今なら間に合います。すぐに修正しましょう！**

**重要**: このシステムは**本番環境で使用してはいけません**。まず緊急パッチを適用してください。

---

*監査者署名: Hestia (hestia-auditor)*  
*次回監査: パッチ適用後24時間以内*