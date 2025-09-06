"""Fix vector dimension from 1536 to 384 for all-MiniLM-L6-v2

Revision ID: 001_fix_vector_dimension
Revises: 
Create Date: 2024-01-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001_fix_vector_dimension'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade to 384-dimension vectors for all-MiniLM-L6-v2."""
    # Drop existing vector index if it exists
    op.execute("DROP INDEX IF EXISTS idx_memories_embedding;")
    
    # Drop the embedding column with old dimension
    op.drop_column('memories', 'embedding')
    
    # Add the embedding column with correct dimension
    op.add_column('memories', 
        sa.Column('embedding', 
                 Vector(384), 
                 nullable=True, 
                 comment="Vector embedding for semantic search (all-MiniLM-L6-v2 dimension)")
    )
    
    # Recreate the vector index with proper dimension
    op.execute("""
        CREATE INDEX idx_memories_embedding 
        ON memories USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
    """)


def downgrade():
    """Downgrade to 1536-dimension vectors (OpenAI ada-002)."""
    # Drop existing vector index
    op.execute("DROP INDEX IF EXISTS idx_memories_embedding;")
    
    # Drop the embedding column with 384 dimension
    op.drop_column('memories', 'embedding')
    
    # Add the embedding column with old dimension
    op.add_column('memories', 
        sa.Column('embedding', 
                 Vector(1536), 
                 nullable=True, 
                 comment="Vector embedding for semantic search (OpenAI ada-002 dimension)")
    )
    
    # Recreate the vector index with old dimension
    op.execute("""
        CREATE INDEX idx_memories_embedding 
        ON memories USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
    """)