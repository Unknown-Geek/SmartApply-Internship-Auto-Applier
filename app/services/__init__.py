# =============================================================================
# SmartApply - Services Module
# =============================================================================
"""
Services Module

Contains business logic services for the application.
"""

from app.services.agent_service import router as agent_router

__all__ = ["agent_router"]
