"""
TMWS - Tactical Memory Warehouse System
FastMCP + FastAPI統合サーバー

Strategic Architect Athena設計による優雅な統合実装
"""

__version__ = "1.0.0"
__author__ = "Strategic Architect Athena"
__description__ = "Unified FastMCP + FastAPI Server for tactical memory operations"

from .unified_server import TMWSUnifiedServer

__all__ = ["TMWSUnifiedServer"]