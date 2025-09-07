#!/usr/bin/env python3
"""
TMWS Migration Script: Personas → Agents
Migrates existing persona-based data to the new agent-centric architecture.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from models.agent import Agent, AgentNamespace
from models.memory import Memory
from models.task import Task
from services.agent_service import AgentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PersonaToAgentMigrator:
    """Handles the migration from Persona-based system to Agent-based system."""
    
    def __init__(self, async_engine, sync_engine):
        self.async_engine = async_engine
        self.sync_engine = sync_engine
        self.async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession)
        self.sync_session_maker = sessionmaker(sync_engine)
        
        self.migration_log = []
        self.errors = []
    
    def log_action(self, action: str, details: Dict[str, Any] = None):
        """Log migration actions for audit trail."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details or {}
        }
        self.migration_log.append(entry)
        logger.info(f"Migration: {action} - {details}")
    
    def log_error(self, error: str, details: Dict[str, Any] = None):
        """Log migration errors."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "details": details or {}
        }
        self.errors.append(entry)
        logger.error(f"Migration Error: {error} - {details}")
    
    async def pre_migration_validation(self) -> bool:
        """Validate system state before migration."""
        async with self.async_session_maker() as session:
            try:
                # Check if personas table exists
                result = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'personas'
                    );
                """))
                personas_table_exists = result.scalar()
                
                if not personas_table_exists:
                    self.log_action("pre_validation", {"status": "no_personas_table"})
                    logger.warning("Personas table does not exist - creating default agents only")
                    return True
                
                # Count existing personas
                persona_count = await session.execute(text("SELECT COUNT(*) FROM personas"))
                persona_count = persona_count.scalar()
                
                # Check if agents table is empty
                agent_count = await session.execute(text("SELECT COUNT(*) FROM agents"))
                agent_count = agent_count.scalar()
                
                self.log_action("pre_validation", {
                    "personas_count": persona_count,
                    "agents_count": agent_count,
                    "status": "ready" if agent_count == 0 else "agents_exist"
                })
                
                if agent_count > 0:
                    logger.warning(f"Agents table already contains {agent_count} entries")
                    return input("Continue migration anyway? (y/N): ").lower() == 'y'
                
                return True
                
            except Exception as e:
                self.log_error("pre_validation_failed", {"error": str(e)})
                return False
    
    async def create_database_schema(self):
        """Create new database tables for agent system."""
        async with self.async_session_maker() as session:
            try:
                # Create agents table
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS agents (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        agent_id TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        agent_type TEXT NOT NULL,
                        agent_subtype TEXT,
                        capabilities JSONB DEFAULT '{}',
                        configuration JSONB DEFAULT '{}',
                        namespace TEXT NOT NULL DEFAULT 'default',
                        access_level TEXT NOT NULL DEFAULT 'standard',
                        is_active BOOLEAN DEFAULT TRUE,
                        last_activity TIMESTAMPTZ DEFAULT NOW(),
                        total_memories INTEGER DEFAULT 0,
                        total_tasks INTEGER DEFAULT 0,
                        performance_score FLOAT DEFAULT 1.0,
                        parent_agent_id TEXT,
                        team_memberships JSONB DEFAULT '[]',
                        learning_enabled BOOLEAN DEFAULT TRUE,
                        adaptation_rate FLOAT DEFAULT 0.1,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        CONSTRAINT agent_id_length CHECK (LENGTH(agent_id) >= 3 AND LENGTH(agent_id) <= 100),
                        CONSTRAINT agent_id_format CHECK (agent_id ~ '^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$'),
                        CONSTRAINT access_level_check CHECK (access_level IN ('admin', 'standard', 'restricted', 'readonly')),
                        CONSTRAINT performance_score_bounds CHECK (performance_score >= 0.0 AND performance_score <= 10.0),
                        CONSTRAINT adaptation_rate_bounds CHECK (adaptation_rate >= 0.0 AND adaptation_rate <= 1.0)
                    );
                """))
                
                # Create agent_namespaces table
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS agent_namespaces (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        namespace TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        description TEXT,
                        parent_namespace TEXT,
                        access_policy TEXT NOT NULL DEFAULT 'private',
                        allowed_agents JSONB DEFAULT '[]',
                        is_active BOOLEAN DEFAULT TRUE,
                        max_agents INTEGER,
                        agent_count INTEGER DEFAULT 0,
                        memory_count INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        CONSTRAINT access_policy_check CHECK (access_policy IN ('public', 'private', 'invite_only', 'restricted')),
                        CONSTRAINT max_agents_positive CHECK (max_agents IS NULL OR max_agents > 0)
                    );
                """))
                
                # Create agent_teams table
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS agent_teams (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        team_id TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        description TEXT,
                        namespace TEXT NOT NULL DEFAULT 'default',
                        team_type TEXT NOT NULL DEFAULT 'collaborative',
                        member_agents JSONB DEFAULT '[]',
                        team_lead TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        max_members INTEGER,
                        completed_workflows INTEGER DEFAULT 0,
                        team_performance_score FLOAT DEFAULT 1.0,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        CONSTRAINT team_type_check CHECK (team_type IN ('collaborative', 'hierarchical', 'specialized')),
                        CONSTRAINT max_members_positive CHECK (max_members IS NULL OR max_members > 0)
                    );
                """))
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);",
                    "CREATE INDEX IF NOT EXISTS idx_agents_namespace_active ON agents(namespace, is_active);",
                    "CREATE INDEX IF NOT EXISTS idx_agents_type_active ON agents(agent_type, is_active);",
                    "CREATE INDEX IF NOT EXISTS idx_agents_last_activity ON agents(last_activity);",
                    "CREATE INDEX IF NOT EXISTS idx_agents_performance ON agents(performance_score);",
                    "CREATE INDEX IF NOT EXISTS idx_namespaces_namespace ON agent_namespaces(namespace);",
                    "CREATE INDEX IF NOT EXISTS idx_namespaces_parent ON agent_namespaces(parent_namespace, is_active);",
                    "CREATE INDEX IF NOT EXISTS idx_teams_team_id ON agent_teams(team_id);",
                    "CREATE INDEX IF NOT EXISTS idx_teams_namespace ON agent_teams(namespace, is_active);"
                ]
                
                for index_sql in indexes:
                    await session.execute(text(index_sql))
                
                await session.commit()
                self.log_action("schema_created", {"tables": ["agents", "agent_namespaces", "agent_teams"]})
                
            except Exception as e:
                await session.rollback()
                self.log_error("schema_creation_failed", {"error": str(e)})
                raise
    
    async def migrate_personas_to_agents(self):
        """Migrate existing personas to agents."""
        async with self.async_session_maker() as session:
            agent_service = AgentService(session)
            
            try:
                # First check if personas table exists
                result = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'personas'
                    );
                """))
                personas_exist = result.scalar()
                
                if not personas_exist:
                    self.log_action("persona_migration", {"status": "no_personas_table"})
                    # Create default Trinitas agents
                    return await self.create_default_agents(agent_service)
                
                # Get all personas
                personas_result = await session.execute(text("""
                    SELECT id, name, type, role, display_name, description, 
                           specialties, capabilities, personality_traits, 
                           is_active, metadata, created_at, updated_at
                    FROM personas
                """))
                personas = personas_result.fetchall()
                
                migrated_count = 0
                for persona in personas:
                    try:
                        # Map persona to agent
                        agent_id = f"{persona.name.lower().replace('_', '-')}-{persona.role.lower()}"
                        
                        # Map persona type/role to agent type
                        type_mapping = {
                            "athena": "system_orchestrator",
                            "artemis": "technical_optimizer", 
                            "hestia": "security_auditor",
                            "bellona": "tactical_coordinator",
                            "hera": "strategic_planner",
                            "seshat": "knowledge_architect"
                        }
                        
                        agent_type = type_mapping.get(persona.type, "general_agent")
                        
                        # Convert capabilities
                        capabilities = {}
                        if persona.capabilities:
                            capabilities = persona.capabilities
                        if persona.specialties:
                            capabilities["specialties"] = persona.specialties
                        
                        # Convert configuration
                        configuration = persona.personality_traits or {}
                        if persona.metadata:
                            configuration.update(persona.metadata)
                        
                        # Create agent
                        agent = await agent_service.create_agent(
                            agent_id=agent_id,
                            display_name=persona.display_name or persona.name,
                            agent_type=agent_type,
                            agent_subtype=persona.role,
                            capabilities=capabilities,
                            configuration=configuration,
                            namespace="trinitas",
                            access_level="standard" if persona.role != "strategist" else "admin"
                        )
                        
                        migrated_count += 1
                        self.log_action("persona_migrated", {
                            "old_id": str(persona.id),
                            "new_agent_id": agent_id,
                            "name": persona.name,
                            "type": agent_type
                        })
                        
                    except Exception as e:
                        self.log_error("persona_migration_failed", {
                            "persona_id": str(persona.id),
                            "persona_name": persona.name,
                            "error": str(e)
                        })
                        continue
                
                self.log_action("persona_migration_complete", {
                    "total_personas": len(personas),
                    "migrated_count": migrated_count,
                    "failed_count": len(personas) - migrated_count
                })
                
                return migrated_count
                
            except Exception as e:
                self.log_error("persona_migration_failed", {"error": str(e)})
                raise
    
    async def create_default_agents(self, agent_service: AgentService) -> int:
        """Create default Trinitas agents."""
        default_agents = Agent.create_default_agents()
        created_count = 0
        
        for agent_data in default_agents:
            try:
                agent = await agent_service.create_agent(**agent_data)
                created_count += 1
                self.log_action("default_agent_created", {
                    "agent_id": agent.agent_id,
                    "display_name": agent.display_name,
                    "agent_type": agent.agent_type
                })
            except Exception as e:
                self.log_error("default_agent_creation_failed", {
                    "agent_id": agent_data["agent_id"],
                    "error": str(e)
                })
        
        return created_count
    
    async def update_memory_schema(self):
        """Update memory table to use agent_id instead of persona_id."""
        async with self.async_session_maker() as session:
            try:
                # Check if persona_id column exists
                result = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'memories' AND column_name = 'persona_id'
                    );
                """))
                persona_id_exists = result.scalar()
                
                if not persona_id_exists:
                    self.log_action("memory_schema_update", {"status": "already_updated"})
                    return
                
                # Add new agent-centric columns
                await session.execute(text("""
                    ALTER TABLE memories 
                    ADD COLUMN IF NOT EXISTS agent_id TEXT,
                    ADD COLUMN IF NOT EXISTS namespace TEXT DEFAULT 'default' NOT NULL,
                    ADD COLUMN IF NOT EXISTS access_level TEXT DEFAULT 'private' NOT NULL,
                    ADD COLUMN IF NOT EXISTS context_tags JSONB DEFAULT '[]',
                    ADD COLUMN IF NOT EXISTS learning_weight FLOAT DEFAULT 1.0,
                    ADD COLUMN IF NOT EXISTS parent_memory_id UUID,
                    ADD COLUMN IF NOT EXISTS memory_category TEXT DEFAULT 'general' NOT NULL,
                    ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 1.0,
                    ADD COLUMN IF NOT EXISTS is_learned BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS is_shared BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS external_references JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS similarity_threshold FLOAT DEFAULT 0.7;
                """))
                
                # Migrate persona_id data to agent_id
                await session.execute(text("""
                    UPDATE memories 
                    SET agent_id = CASE
                        WHEN EXISTS (SELECT 1 FROM personas WHERE personas.id = memories.persona_id) 
                        THEN (
                            SELECT LOWER(personas.name) || '-' || LOWER(personas.role)
                            FROM personas 
                            WHERE personas.id = memories.persona_id
                        )
                        ELSE NULL
                    END
                    WHERE persona_id IS NOT NULL;
                """))
                
                # Add constraints and indexes
                await session.execute(text("""
                    ALTER TABLE memories 
                    ADD CONSTRAINT IF NOT EXISTS access_level_check 
                        CHECK (access_level IN ('private', 'shared', 'public', 'system')),
                    ADD CONSTRAINT IF NOT EXISTS learning_weight_bounds 
                        CHECK (learning_weight >= 0.0 AND learning_weight <= 10.0),
                    ADD CONSTRAINT IF NOT EXISTS relevance_score_bounds 
                        CHECK (relevance_score >= 0.0 AND relevance_score <= 10.0),
                    ADD CONSTRAINT IF NOT EXISTS similarity_threshold_bounds 
                        CHECK (similarity_threshold >= 0.0 AND similarity_threshold <= 1.0);
                """))
                
                # Create new indexes
                memory_indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_memories_agent_namespace ON memories(agent_id, namespace);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_access_level ON memories(access_level, is_archived);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_category_type ON memories(memory_category, memory_type);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_learning ON memories(is_learned, learning_weight);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_shared ON memories(is_shared, access_level);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_hierarchy ON memories(parent_memory_id, memory_category);",
                    "CREATE INDEX IF NOT EXISTS idx_memories_context_tags ON memories USING gin(context_tags);"
                ]
                
                for index_sql in memory_indexes:
                    await session.execute(text(index_sql))
                
                await session.commit()
                self.log_action("memory_schema_updated", {"status": "success"})
                
            except Exception as e:
                await session.rollback()
                self.log_error("memory_schema_update_failed", {"error": str(e)})
                raise
    
    async def update_task_schema(self):
        """Update task table to use agent_id instead of assigned_persona_id."""
        async with self.async_session_maker() as session:
            try:
                # Check if assigned_persona_id column exists
                result = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'tasks' AND column_name = 'assigned_persona_id'
                    );
                """))
                persona_id_exists = result.scalar()
                
                if not persona_id_exists:
                    self.log_action("task_schema_update", {"status": "already_updated"})
                    return
                
                # Add new agent-centric columns
                await session.execute(text("""
                    ALTER TABLE tasks
                    ADD COLUMN IF NOT EXISTS assigned_agent_id TEXT,
                    ADD COLUMN IF NOT EXISTS collaborating_agents JSONB DEFAULT '[]',
                    ADD COLUMN IF NOT EXISTS namespace TEXT DEFAULT 'default' NOT NULL,
                    ADD COLUMN IF NOT EXISTS access_level TEXT DEFAULT 'private' NOT NULL,
                    ADD COLUMN IF NOT EXISTS context_tags JSONB DEFAULT '[]',
                    ADD COLUMN IF NOT EXISTS parent_task_id UUID,
                    ADD COLUMN IF NOT EXISTS task_config JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS input_data JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS output_data JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS progress_percentage FLOAT DEFAULT 0.0,
                    ADD COLUMN IF NOT EXISTS estimated_duration INTEGER,
                    ADD COLUMN IF NOT EXISTS actual_duration INTEGER,
                    ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3,
                    ADD COLUMN IF NOT EXISTS error_message TEXT,
                    ADD COLUMN IF NOT EXISTS error_details JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS execution_log JSONB DEFAULT '[]',
                    ADD COLUMN IF NOT EXISTS resource_requirements JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS resource_usage JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS quality_score FLOAT,
                    ADD COLUMN IF NOT EXISTS success_criteria JSONB DEFAULT '{}';
                """))
                
                # Migrate assigned_persona_id data to assigned_agent_id
                await session.execute(text("""
                    UPDATE tasks 
                    SET assigned_agent_id = CASE
                        WHEN EXISTS (SELECT 1 FROM personas WHERE personas.id = tasks.assigned_persona_id) 
                        THEN (
                            SELECT LOWER(personas.name) || '-' || LOWER(personas.role)
                            FROM personas 
                            WHERE personas.id = tasks.assigned_persona_id
                        )
                        ELSE NULL
                    END
                    WHERE assigned_persona_id IS NOT NULL;
                """))
                
                # Add constraints
                await session.execute(text("""
                    ALTER TABLE tasks 
                    ADD CONSTRAINT IF NOT EXISTS access_level_check 
                        CHECK (access_level IN ('private', 'shared', 'public', 'system')),
                    ADD CONSTRAINT IF NOT EXISTS progress_bounds 
                        CHECK (progress_percentage >= 0.0 AND progress_percentage <= 100.0),
                    ADD CONSTRAINT IF NOT EXISTS estimated_duration_positive 
                        CHECK (estimated_duration IS NULL OR estimated_duration > 0),
                    ADD CONSTRAINT IF NOT EXISTS actual_duration_non_negative 
                        CHECK (actual_duration IS NULL OR actual_duration >= 0),
                    ADD CONSTRAINT IF NOT EXISTS retry_count_non_negative 
                        CHECK (retry_count >= 0),
                    ADD CONSTRAINT IF NOT EXISTS max_retries_non_negative 
                        CHECK (max_retries >= 0),
                    ADD CONSTRAINT IF NOT EXISTS quality_score_bounds 
                        CHECK (quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 10.0));
                """))
                
                # Create new indexes
                task_indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_tasks_agent_status ON tasks(assigned_agent_id, status);",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_namespace_status ON tasks(namespace, status);",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_hierarchy ON tasks(parent_task_id, status);",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_progress ON tasks(progress_percentage);",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_performance ON tasks(quality_score, actual_duration);",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_context_tags ON tasks USING gin(context_tags);"
                ]
                
                for index_sql in task_indexes:
                    await session.execute(text(index_sql))
                
                await session.commit()
                self.log_action("task_schema_updated", {"status": "success"})
                
            except Exception as e:
                await session.rollback()
                self.log_error("task_schema_update_failed", {"error": str(e)})
                raise
    
    async def create_default_namespaces(self):
        """Create default namespaces."""
        async with self.async_session_maker() as session:
            agent_service = AgentService(session)
            
            default_namespaces = [
                {
                    "namespace": "default",
                    "display_name": "Default Namespace",
                    "description": "Default namespace for general use",
                    "access_policy": "public"
                },
                {
                    "namespace": "trinitas",
                    "display_name": "Trinitas System",
                    "description": "Namespace for Trinitas core agents",
                    "access_policy": "restricted"
                },
                {
                    "namespace": "public",
                    "display_name": "Public Namespace", 
                    "description": "Public namespace accessible to all agents",
                    "access_policy": "public"
                },
                {
                    "namespace": "system",
                    "display_name": "System Namespace",
                    "description": "System-level namespace for administrative functions",
                    "access_policy": "restricted"
                }
            ]
            
            created_count = 0
            for ns_data in default_namespaces:
                try:
                    await agent_service.create_namespace(**ns_data)
                    created_count += 1
                    self.log_action("namespace_created", ns_data)
                except Exception as e:
                    self.log_error("namespace_creation_failed", {
                        "namespace": ns_data["namespace"],
                        "error": str(e)
                    })
            
            return created_count
    
    async def post_migration_validation(self) -> bool:
        """Validate migration results."""
        async with self.async_session_maker() as session:
            try:
                # Count agents
                agent_count = await session.execute(text("SELECT COUNT(*) FROM agents"))
                agent_count = agent_count.scalar()
                
                # Count namespaces
                namespace_count = await session.execute(text("SELECT COUNT(*) FROM agent_namespaces"))
                namespace_count = namespace_count.scalar()
                
                # Count memories with agent_id
                memory_agent_count = await session.execute(text("""
                    SELECT COUNT(*) FROM memories WHERE agent_id IS NOT NULL
                """))
                memory_agent_count = memory_agent_count.scalar()
                
                # Count tasks with assigned_agent_id
                task_agent_count = await session.execute(text("""
                    SELECT COUNT(*) FROM tasks WHERE assigned_agent_id IS NOT NULL
                """))
                task_agent_count = task_agent_count.scalar()
                
                validation_results = {
                    "agents_created": agent_count,
                    "namespaces_created": namespace_count,
                    "memories_with_agents": memory_agent_count,
                    "tasks_with_agents": task_agent_count,
                    "migration_errors": len(self.errors)
                }
                
                self.log_action("post_migration_validation", validation_results)
                
                # Basic validation checks
                success = (
                    agent_count > 0 and 
                    namespace_count > 0 and
                    len(self.errors) == 0
                )
                
                return success
                
            except Exception as e:
                self.log_error("post_validation_failed", {"error": str(e)})
                return False
    
    async def run_migration(self) -> Dict[str, Any]:
        """Run the complete migration process."""
        start_time = datetime.utcnow()
        self.log_action("migration_started", {"start_time": start_time.isoformat()})
        
        try:
            # Pre-migration validation
            if not await self.pre_migration_validation():
                raise Exception("Pre-migration validation failed")
            
            # Create new schema
            await self.create_database_schema()
            
            # Create default namespaces
            namespace_count = await self.create_default_namespaces()
            
            # Migrate personas to agents
            agent_count = await self.migrate_personas_to_agents()
            
            # Update memory schema
            await self.update_memory_schema()
            
            # Update task schema  
            await self.update_task_schema()
            
            # Post-migration validation
            validation_success = await self.post_migration_validation()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            results = {
                "success": validation_success,
                "duration_seconds": duration,
                "agents_created": agent_count,
                "namespaces_created": namespace_count,
                "errors": len(self.errors),
                "migration_log_entries": len(self.migration_log)
            }
            
            self.log_action("migration_completed", results)
            return results
            
        except Exception as e:
            self.log_error("migration_failed", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "errors": len(self.errors),
                "migration_log_entries": len(self.migration_log)
            }
    
    def save_migration_report(self, results: Dict[str, Any]):
        """Save migration report to file."""
        import json
        
        report = {
            "migration_summary": results,
            "migration_log": self.migration_log,
            "errors": self.errors,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        report_file = Path(__file__).parent / f"migration_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Migration report saved to: {report_file}")
        return report_file


async def main():
    """Main migration function."""
    settings = get_settings()
    
    # Create engines
    async_engine = create_async_engine(settings.async_database_url)
    sync_engine = create_engine(settings.database_url)
    
    # Create migrator
    migrator = PersonaToAgentMigrator(async_engine, sync_engine)
    
    logger.info("🚀 Starting TMWS Persona → Agent Migration")
    logger.info("=" * 60)
    
    # Run migration
    results = await migrator.run_migration()
    
    # Save report
    report_file = migrator.save_migration_report(results)
    
    # Print summary
    logger.info("=" * 60)
    logger.info("🎯 Migration Summary:")
    logger.info(f"   Success: {results.get('success', False)}")
    logger.info(f"   Duration: {results.get('duration_seconds', 0):.1f} seconds")
    logger.info(f"   Agents Created: {results.get('agents_created', 0)}")
    logger.info(f"   Namespaces Created: {results.get('namespaces_created', 0)}")
    logger.info(f"   Errors: {results.get('errors', 0)}")
    logger.info(f"   Report: {report_file}")
    
    if results.get('success'):
        logger.info("✅ Migration completed successfully!")
        logger.info("🔄 Next steps:")
        logger.info("   1. Verify agent functionality with test queries")
        logger.info("   2. Update client applications to use agent APIs")
        logger.info("   3. Consider dropping old persona tables after verification")
    else:
        logger.error("❌ Migration failed!")
        logger.error("🔍 Check the migration report for detailed error information")
        if 'error' in results:
            logger.error(f"   Primary error: {results['error']}")
    
    # Cleanup
    await async_engine.dispose()
    sync_engine.dispose()
    
    return results.get('success', False)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)