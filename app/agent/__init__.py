# =============================================================================
# SmartApply — Agent Module
# =============================================================================
# Cerebras-powered autonomous agent for internship applications.
# =============================================================================

"""
Agent Module

Contains the Cerebras agent, browser manager, and orchestration logic.
"""

from app.agent.cerebras_agent import CerebrasAgent, AgentResult
from app.agent.orchestrator import SmartApplyOrchestrator

__all__ = [
    "CerebrasAgent",
    "AgentResult",
    "SmartApplyOrchestrator",
]
