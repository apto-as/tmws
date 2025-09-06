-- TMWS Database Schema
-- Vector dimension: 384 (all-MiniLM-L6-v2)
-- Fixed from previous 1536 (OpenAI ada-002)

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create personas table
CREATE TABLE IF NOT EXISTS personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Persona identification
    name TEXT NOT NULL UNIQUE,
    type VARCHAR NOT NULL CHECK (type IN ('athena', 'artemis', 'hestia', 'bellona', 'seshat')),
    role VARCHAR NOT NULL CHECK (role IN ('strategist', 'optimizer', 'auditor', 'coordinator', 'documenter')),
    
    -- Persona configuration
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    specialties JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Behavior configuration
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Status and capabilities
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Performance metrics
    total_tasks INTEGER NOT NULL DEFAULT 0,
    successful_tasks INTEGER NOT NULL DEFAULT 0,
    average_response_time FLOAT,
    
    -- Additional timestamps
    last_active_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for personas
CREATE INDEX idx_personas_name ON personas(name);
CREATE INDEX idx_personas_type ON personas(type);
CREATE INDEX idx_personas_role ON personas(role);
CREATE INDEX idx_personas_is_active ON personas(is_active);
CREATE INDEX idx_personas_type_active ON personas(type, is_active);
CREATE INDEX idx_personas_role_active ON personas(role, is_active);
CREATE INDEX idx_personas_active_last_active ON personas(is_active, last_active_at);

-- Create memories table with correct vector dimension
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Core content
    content TEXT NOT NULL CHECK (content != ''),
    
    -- Vector embedding - FIXED DIMENSION: 384 for all-MiniLM-L6-v2
    embedding vector(384),
    
    -- Access tracking
    accessed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    access_count INTEGER NOT NULL DEFAULT 0,
    
    -- Performance metrics
    recall_count INTEGER NOT NULL DEFAULT 0,
    last_recalled_at TIMESTAMP WITH TIME ZONE,
    
    -- Search optimization
    importance FLOAT NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    decay_rate FLOAT NOT NULL DEFAULT 0.1 CHECK (decay_rate >= 0 AND decay_rate <= 1),
    
    -- Relationships
    persona_id UUID REFERENCES personas(id) ON DELETE SET NULL,
    related_memories JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Tags and categorization
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    context_type TEXT,
    
    -- Generated columns for performance
    -- Note: Actual generated columns would be added after base columns
    content_length INTEGER GENERATED ALWAYS AS (LENGTH(content)) STORED,
    has_embedding BOOLEAN GENERATED ALWAYS AS (embedding IS NOT NULL) STORED
);

-- Create indexes for memories
CREATE INDEX idx_memories_persona_id ON memories(persona_id);
CREATE INDEX idx_memories_importance ON memories(importance DESC);
CREATE INDEX idx_memories_accessed_at ON memories(accessed_at DESC);
CREATE INDEX idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX idx_memories_context_type ON memories(context_type) WHERE context_type IS NOT NULL;
CREATE INDEX idx_memories_has_embedding ON memories(has_embedding) WHERE has_embedding = true;
CREATE INDEX idx_memories_tags ON memories USING GIN (tags);
CREATE INDEX idx_memories_metadata ON memories USING GIN (metadata);

-- Create vector similarity search index (HNSW for better performance)
CREATE INDEX idx_memories_embedding ON memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Task identification
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'general',
    
    -- Task status and priority
    status VARCHAR NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled', 'skipped')),
    priority VARCHAR NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    
    -- Progress tracking
    progress FLOAT NOT NULL DEFAULT 0.0 CHECK (progress >= 0 AND progress <= 1),
    
    -- Assignment
    assigned_persona_id UUID REFERENCES personas(id) ON DELETE SET NULL,
    
    -- Task dependencies
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Results and errors
    result JSONB,
    error_message TEXT,
    
    -- Execution tracking
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Retry tracking
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    
    -- Tags for categorization
    tags JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- Create indexes for tasks
CREATE INDEX idx_tasks_title ON tasks(title);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_assigned_persona_id ON tasks(assigned_persona_id);
CREATE INDEX idx_tasks_status_priority ON tasks(status, priority);
CREATE INDEX idx_tasks_assigned_status ON tasks(assigned_persona_id, status);
CREATE INDEX idx_tasks_created_status ON tasks(created_at, status);
CREATE INDEX idx_tasks_started_at ON tasks(started_at);
CREATE INDEX idx_tasks_completed_at ON tasks(completed_at);

-- Create workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Workflow identification
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    
    -- Workflow configuration
    workflow_type VARCHAR NOT NULL DEFAULT 'sequential' CHECK (workflow_type IN ('sequential', 'parallel', 'conditional', 'hybrid')),
    
    -- Workflow status
    status VARCHAR NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'inactive', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    
    -- Workflow definition
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Execution tracking
    current_step_index INTEGER NOT NULL DEFAULT 0,
    execution_count INTEGER NOT NULL DEFAULT 0,
    
    -- Execution timestamps
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_executed_at TIMESTAMP WITH TIME ZONE,
    
    -- Error tracking
    error_message TEXT,
    failed_step_index INTEGER,
    
    -- Creator information
    created_by TEXT,
    
    -- Tags for categorization
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Execution configuration
    config JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Create indexes for workflows
CREATE INDEX idx_workflows_name ON workflows(name);
CREATE INDEX idx_workflows_workflow_type ON workflows(workflow_type);
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_status_type ON workflows(status, workflow_type);
CREATE INDEX idx_workflows_created_by ON workflows(created_by);
CREATE INDEX idx_workflows_created_by_status ON workflows(created_by, status);
CREATE INDEX idx_workflows_last_executed ON workflows(last_executed_at);
CREATE INDEX idx_workflows_started_at ON workflows(started_at);
CREATE INDEX idx_workflows_completed_at ON workflows(completed_at);

-- Create update trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to all tables
CREATE TRIGGER update_personas_updated_at BEFORE UPDATE ON personas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default personas
INSERT INTO personas (name, type, role, display_name, description, specialties, capabilities)
VALUES 
    ('athena', 'athena', 'strategist', 'Athena - Strategic Architect', 
     'Strategic planning and architecture design specialist',
     '["strategic_planning", "architecture_design", "team_coordination", "stakeholder_management", "long_term_vision"]'::jsonb,
     '["system_architecture", "project_planning", "risk_assessment", "resource_optimization", "stakeholder_communication"]'::jsonb),
    
    ('artemis', 'artemis', 'optimizer', 'Artemis - Technical Perfectionist',
     'Performance optimization and code quality specialist',
     '["performance_optimization", "code_quality", "technical_excellence", "algorithm_design", "efficiency_improvement"]'::jsonb,
     '["code_optimization", "performance_tuning", "quality_assurance", "refactoring", "best_practices"]'::jsonb),
    
    ('hestia', 'hestia', 'auditor', 'Hestia - Security Guardian',
     'Security analysis and vulnerability assessment specialist',
     '["security_analysis", "vulnerability_assessment", "risk_management", "threat_modeling", "quality_assurance"]'::jsonb,
     '["security_audit", "vulnerability_scanning", "risk_analysis", "compliance_checking", "threat_assessment"]'::jsonb),
    
    ('bellona', 'bellona', 'coordinator', 'Bellona - Tactical Coordinator',
     'Parallel task management and resource optimization specialist',
     '["task_coordination", "resource_optimization", "parallel_execution", "workflow_orchestration", "real_time_coordination"]'::jsonb,
     '["task_management", "resource_allocation", "parallel_processing", "workflow_automation", "coordination"]'::jsonb),
    
    ('seshat', 'seshat', 'documenter', 'Seshat - Knowledge Architect',
     'Documentation creation and knowledge management specialist',
     '["documentation_creation", "knowledge_management", "information_architecture", "content_organization", "system_documentation"]'::jsonb,
     '["documentation_generation", "knowledge_archival", "content_creation", "information_structuring", "API_documentation"]'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- Create function for semantic search using cosine similarity
CREATE OR REPLACE FUNCTION search_memories_semantic(
    query_embedding vector(384),
    limit_count INTEGER DEFAULT 10,
    threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    similarity FLOAT,
    importance FLOAT,
    persona_id UUID,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.content,
        1 - (m.embedding <=> query_embedding) AS similarity,
        m.importance,
        m.persona_id,
        m.created_at
    FROM memories m
    WHERE m.embedding IS NOT NULL
    AND 1 - (m.embedding <=> query_embedding) > threshold
    ORDER BY m.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to update memory access tracking
CREATE OR REPLACE FUNCTION update_memory_access(memory_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE memories
    SET 
        accessed_at = NOW(),
        access_count = access_count + 1,
        recall_count = recall_count + 1,
        last_recalled_at = NOW()
    WHERE id = memory_id;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions to tmws_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tmws_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tmws_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO tmws_user;