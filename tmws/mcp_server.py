#!/usr/bin/env python3
"""
TMWS MCP Server Module
Package-compatible MCP server entry point
"""

import sys
from pathlib import Path

# Add src to Python path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    """Main entry point for MCP server"""
    from src.mcp_server_v2 import mcp
    mcp.run()

if __name__ == "__main__":
    main()