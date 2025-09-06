"""
TMWS - Trinitas Memory & Workflow Service
Enhanced with Bellona's Tactical Coordination System
"""

__version__ = "1.0.0"

# Core tactical coordination exports
from .core.tactical_coordinator import TacticalCoordinator, create_tactical_coordinator
from .core.process_manager import (
    TacticalProcessManager,
    ServiceState,
    ProcessPriority,
    create_tactical_process_manager
)

__all__ = [
    "TacticalCoordinator",
    "create_tactical_coordinator", 
    "TacticalProcessManager",
    "ServiceState",
    "ProcessPriority",
    "create_tactical_process_manager"
]