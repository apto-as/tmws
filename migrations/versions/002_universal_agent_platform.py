"""Universal Agent Platform migration

Revision ID: 002
Revises: 001
Create Date: 2025-01-06

This migration transforms TMWS from a persona-specific system to a universal
multi-agent memory management platform.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector
import json

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade to universal agent platform."""
    
    # Create AccessLevel enum
    op.execute("CREATE TYPE accesslevel AS ENUM ('private', 'team', 'shared', 'public', 'system')")
    op.execute("CREATE TYPE agentstatus AS ENUM ('active', 'inactive', 'suspended', 'deprecated')")
    
    # 1. Create new agent tables
    op.create_table('agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('organization_id', sa.Text(), nullable=True),
        sa.Column('namespace', sa.Text(), nullable=False, server_default='default'),
        sa.Column('agent_type', sa.Text(), nullable=True),
        sa.Column('capabilities', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('default_access_level', postgresql.ENUM('private', 'team', 'shared', 'public', 'system', name='accesslevel'), nullable=False, server_default='private'),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'suspended', 'deprecated', name='agentstatus'), nullable=False, server_default='active'),
        sa.Column('health_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('total_memories', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tasks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_tasks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_response_time_ms', sa.Float(), nullable=True),
        sa.Column('api_key_hash', sa.Text(), nullable=True),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id')
    )
    
    op.create_index('ix_agents_agent_id', 'agents', ['agent_id'])
    op.create_index('ix_agents_organization_id', 'agents', ['organization_id'])
    op.create_index('ix_agents_namespace', 'agents', ['namespace'])
    op.create_index('ix_agent_org_namespace', 'agents', ['organization_id', 'namespace'])
    op.create_index('ix_agent_status_active', 'agents', ['status', 'last_active_at'])
    op.create_index('ix_agent_type_status', 'agents', ['agent_type', 'status'])
    
    # 2. Create agent teams table
    op.create_table('agent_teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=False),
        sa.Column('team_name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('members', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('leader_agent_id', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('shared_namespace', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id')
    )
    
    op.create_index('ix_agent_teams_team_id', 'agent_teams', ['team_id'])
    op.create_index('ix_agent_teams_is_active', 'agent_teams', ['is_active'])
    
    # 3. Create agent namespaces table
    op.create_table('agent_namespaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('namespace', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_agent_id', sa.Text(), nullable=True),
        sa.Column('admin_agents', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('member_agents', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('default_access_level', postgresql.ENUM('private', 'team', 'shared', 'public', 'system', name='accesslevel'), nullable=False, server_default='private'),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('namespace')
    )
    
    op.create_index('ix_agent_namespaces_namespace', 'agent_namespaces', ['namespace'])
    op.create_index('ix_agent_namespaces_is_active', 'agent_namespaces', ['is_active'])
    
    # 4. Create new memories_v2 table
    op.create_table('memories_v2',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('agent_id', sa.Text(), nullable=False),
        sa.Column('namespace', sa.Text(), nullable=False, server_default='default'),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('access_level', postgresql.ENUM('private', 'team', 'shared', 'public', 'system', name='accesslevel'), nullable=False, server_default='private'),
        sa.Column('shared_with_agents', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('learning_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('pattern_ids', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_memory_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['parent_memory_id'], ['memories_v2.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_memory_agent_namespace', 'memories_v2', ['agent_id', 'namespace'])
    op.create_index('ix_memory_access_level', 'memories_v2', ['access_level', 'agent_id'])
    op.create_index('ix_memory_importance', 'memories_v2', ['importance_score', 'relevance_score'])
    op.create_index('ix_memory_accessed', 'memories_v2', ['accessed_at', 'access_count'])
    op.create_index('ix_memory_expires', 'memories_v2', ['expires_at'])
    
    # Create vector index for semantic search
    op.execute("CREATE INDEX ix_memory_embedding ON memories_v2 USING ivfflat (embedding vector_cosine_ops)")
    
    # Create GIN indexes for JSON fields
    op.execute("CREATE INDEX ix_memory_tags ON memories_v2 USING gin (tags)")
    op.execute("CREATE INDEX ix_memory_context ON memories_v2 USING gin (context)")
    
    # 5. Create memory sharing table
    op.create_table('memory_sharing',
        sa.Column('memory_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shared_with_agent_id', sa.Text(), nullable=False),
        sa.Column('permission', sa.Text(), nullable=False, server_default='read'),
        sa.Column('shared_by_agent_id', sa.Text(), nullable=False),
        sa.Column('shared_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['memory_id'], ['memories_v2.id'], ),
        sa.PrimaryKeyConstraint('memory_id', 'shared_with_agent_id')
    )
    
    op.create_index('ix_sharing_agent', 'memory_sharing', ['shared_with_agent_id', 'shared_at'])
    op.create_index('ix_sharing_expires', 'memory_sharing', ['expires_at'])
    
    # 6. Create memory patterns table
    op.create_table('memory_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pattern_type', sa.Text(), nullable=False),
        sa.Column('agent_id', sa.Text(), nullable=False),
        sa.Column('namespace', sa.Text(), nullable=False),
        sa.Column('pattern_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('frequency', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('memory_ids', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_pattern_agent_type', 'memory_patterns', ['agent_id', 'pattern_type'])
    op.create_index('ix_pattern_confidence', 'memory_patterns', ['confidence', 'frequency'])
    op.create_index('ix_memory_patterns_is_active', 'memory_patterns', ['is_active'])
    op.create_index('ix_memory_patterns_agent_id', 'memory_patterns', ['agent_id'])
    op.create_index('ix_memory_patterns_namespace', 'memory_patterns', ['namespace'])
    
    # 7. Create memory consolidations table
    op.create_table('memory_consolidations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_memory_ids', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('consolidated_memory_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consolidation_type', sa.Text(), nullable=False),
        sa.Column('agent_id', sa.Text(), nullable=False),
        sa.Column('consolidation_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['consolidated_memory_id'], ['memories_v2.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_memory_consolidations_agent_id', 'memory_consolidations', ['agent_id'])
    
    # 8. Migrate existing personas to agents
    op.execute("""
        INSERT INTO agents (id, agent_id, display_name, namespace, agent_type, capabilities, config, status)
        SELECT 
            id,
            name as agent_id,
            display_name,
            'trinitas' as namespace,
            CASE role
                WHEN 'strategist' THEN 'strategist'
                WHEN 'optimizer' THEN 'optimizer'
                WHEN 'auditor' THEN 'auditor'
                WHEN 'coordinator' THEN 'coordinator'
                WHEN 'documenter' THEN 'documenter'
                ELSE 'general'
            END as agent_type,
            jsonb_build_object(
                'specialties', specialties,
                'capabilities', capabilities
            ) as capabilities,
            jsonb_build_object(
                'preferences', preferences,
                'original_config', config
            ) as config,
            CASE WHEN is_active THEN 'active'::agentstatus ELSE 'inactive'::agentstatus END as status
        FROM personas
        WHERE EXISTS (SELECT 1 FROM personas)
    """)
    
    # 9. Migrate existing memories
    op.execute("""
        INSERT INTO memories_v2 (
            id, content, agent_id, namespace, embedding, 
            importance_score, tags, context, created_at, updated_at, metadata
        )
        SELECT 
            m.id,
            m.content,
            COALESCE(p.name, 'system') as agent_id,
            COALESCE(m.category, 'default') as namespace,
            m.embedding,
            COALESCE(m.importance, 0.5) as importance_score,
            COALESCE(m.tags, '[]'::jsonb) as tags,
            COALESCE(m.context, '{}'::jsonb) as context,
            m.created_at,
            m.updated_at,
            m.metadata
        FROM memories m
        LEFT JOIN personas p ON m.persona_id = p.id
        WHERE EXISTS (SELECT 1 FROM memories)
    """)
    
    print("✅ Migration completed successfully!")
    print("✅ Existing personas have been migrated to agents")
    print("✅ Existing memories have been migrated to memories_v2")


def downgrade():
    """Downgrade from universal agent platform."""
    
    # Drop new tables
    op.drop_table('memory_consolidations')
    op.drop_table('memory_patterns')
    op.drop_table('memory_sharing')
    op.drop_table('memories_v2')
    op.drop_table('agent_namespaces')
    op.drop_table('agent_teams')
    op.drop_table('agents')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS accesslevel")
    op.execute("DROP TYPE IF EXISTS agentstatus")