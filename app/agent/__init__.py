# =============================================================================
# SmartApply Web Agent - Agent Module
# =============================================================================
# This module contains the web automation agent components.
# =============================================================================

"""
Agent Module

Contains browser-use web agent setup and Gemini LLM integration.
"""

from app.agent.web_agent import WebAgent, create_web_agent

__all__ = ["WebAgent", "create_web_agent"]
