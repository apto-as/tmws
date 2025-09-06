#!/usr/bin/env python3
"""
TMWS MCP Server Entry Point
Launch script for the MCP server
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run the MCP server v2
from src.mcp_server_v2 import mcp

if __name__ == "__main__":
    mcp.run()