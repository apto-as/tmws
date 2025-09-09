#!/usr/bin/env python
"""
Database setup script for TMWS.
Creates all required tables in PostgreSQL.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tmws.core.database import create_tables


async def main():
    """Create all database tables."""
    print("=" * 60)
    print("TMWS Database Setup")
    print("=" * 60)
    
    try:
        print("\n🔄 Creating database tables...")
        await create_tables()
        print("✅ All tables created successfully!")
        
        print("\n📊 Created tables:")
        print("  - agents (Agent registry)")
        print("  - agent_namespaces (Namespace management)")
        print("  - agent_teams (Team associations)")
        print("  - memories (Semantic memory storage)")
        print("  - personas (Persona definitions)")
        print("  - tasks (Task management)")
        print("  - workflows (Workflow orchestration)")
        
        print("\n✨ Database setup complete!")
        print("\nYou can now run TMWS with:")
        print("  uvx --from git+https://github.com/apto-as/tmws.git tmws")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'tmws' exists")
        print("3. User 'tmws_user' has proper permissions")
        print("4. Extensions 'vector' and 'pg_trgm' are installed")
        print("5. .env file is configured with correct DATABASE_URL")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())