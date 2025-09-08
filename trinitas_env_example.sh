#!/bin/bash
# Trinitas Agents 環境変数設定例
# このスクリプトを source コマンドで読み込んで使用します
# 使用方法: source trinitas_env_example.sh athena

# エージェント選択
AGENT_NAME=${1:-athena}

# 共通設定
export TMWS_DATABASE_URL="postgresql://tmws_user:secure_password@localhost:5432/tmws_trinitas"
export TMWS_ENVIRONMENT="production"
export TMWS_AGENT_NAMESPACE="trinitas"
export TMWS_AUTH_ENABLED="true"
export TMWS_MCP_ENABLED="true"
export TMWS_LOG_LEVEL="INFO"

# ベクトル検索設定
export TMWS_EMBEDDING_MODEL="all-MiniLM-L6-v2"
export TMWS_VECTOR_DIMENSION="384"
export TMWS_MAX_EMBEDDING_BATCH_SIZE="32"

# API設定
export TMWS_API_HOST="127.0.0.1"
export TMWS_API_PORT="8000"
export TMWS_CORS_ORIGINS='["http://localhost:3000"]'

# レート制限
export TMWS_RATE_LIMIT_ENABLED="true"
export TMWS_RATE_LIMIT_REQUESTS="1000"
export TMWS_RATE_LIMIT_PERIOD="60"

# エージェント別設定
case $AGENT_NAME in
  "athena")
    export TMWS_AGENT_ID="athena-conductor"
    export TMWS_SECRET_KEY="athena-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "orchestration": true,
      "workflow_automation": true,
      "resource_optimization": true,
      "parallel_execution": true,
      "task_delegation": true,
      "system_coordination": true
    }'
    export TMWS_TACTICAL_MODE="balanced"
    echo "✨ Athena (Harmonious Conductor) 環境変数を設定しました"
    ;;
    
  "artemis")
    export TMWS_AGENT_ID="artemis-optimizer"
    export TMWS_SECRET_KEY="artemis-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "performance_optimization": true,
      "code_quality": true,
      "technical_excellence": true,
      "algorithm_design": true,
      "efficiency_improvement": true,
      "best_practices": true
    }'
    export TMWS_TACTICAL_MODE="aggressive"
    echo "🏹 Artemis (Technical Perfectionist) 環境変数を設定しました"
    ;;
    
  "hestia")
    export TMWS_AGENT_ID="hestia-auditor"
    export TMWS_SECRET_KEY="hestia-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "security_analysis": true,
      "vulnerability_assessment": true,
      "risk_management": true,
      "threat_modeling": true,
      "compliance_verification": true,
      "audit_logging": true
    }'
    export TMWS_TACTICAL_MODE="defensive"
    export TMWS_SECURITY_HEADERS_ENABLED="true"
    export TMWS_AUDIT_LOG_ENABLED="true"
    export TMWS_SECURITY_LOG_ENABLED="true"
    export TMWS_MAX_LOGIN_ATTEMPTS="3"
    export TMWS_LOCKOUT_DURATION_MINUTES="30"
    echo "🔥 Hestia (Security Guardian) 環境変数を設定しました"
    ;;
    
  "eris")
    export TMWS_AGENT_ID="eris-coordinator"
    export TMWS_SECRET_KEY="eris-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "tactical_planning": true,
      "team_coordination": true,
      "conflict_resolution": true,
      "workflow_orchestration": true,
      "collaboration": true,
      "balance_adjustment": true
    }'
    export TMWS_TACTICAL_MODE="balanced"
    echo "⚔️ Eris (Tactical Coordinator) 環境変数を設定しました"
    ;;
    
  "hera")
    export TMWS_AGENT_ID="hera-strategist"
    export TMWS_SECRET_KEY="hera-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "strategic_planning": true,
      "architecture_design": true,
      "long_term_vision": true,
      "roadmap_development": true,
      "stakeholder_management": true,
      "user_experience": true
    }'
    export TMWS_TACTICAL_MODE="balanced"
    echo "🎭 Hera (Strategic Commander) 環境変数を設定しました"
    ;;
    
  "muses")
    export TMWS_AGENT_ID="muses-documenter"
    export TMWS_SECRET_KEY="muses-secret-key-$(openssl rand -hex 16)"
    export TMWS_AGENT_CAPABILITIES='{
      "documentation": true,
      "knowledge_management": true,
      "specification_writing": true,
      "api_documentation": true,
      "archive_management": true,
      "content_structuring": true
    }'
    echo "📚 Muses (Knowledge Architect) 環境変数を設定しました"
    ;;
    
  *)
    echo "❌ 不明なエージェント: $AGENT_NAME"
    echo "使用可能なエージェント: athena, artemis, hestia, eris, hera, muses"
    return 1
    ;;
esac

# 設定確認
echo ""
echo "設定された環境変数:"
echo "  TMWS_AGENT_ID: $TMWS_AGENT_ID"
echo "  TMWS_AGENT_NAMESPACE: $TMWS_AGENT_NAMESPACE"
echo "  TMWS_ENVIRONMENT: $TMWS_ENVIRONMENT"
echo "  TMWS_DATABASE_URL: $TMWS_DATABASE_URL"
echo ""
echo "TMWSを起動するには:"
echo "  python tmws/mcp_server.py"
echo "または:"
echo "  uvx --from git+https://github.com/apto-as/tmws.git tmws"