#!/usr/bin/env python3
"""
TMWS MCP Server Module
Package-compatible MCP server entry point
"""

def main():
    """Main entry point for MCP server"""
    from tmws.mcp_server_v2 import mcp
    mcp.run()

if __name__ == "__main__":
    main()