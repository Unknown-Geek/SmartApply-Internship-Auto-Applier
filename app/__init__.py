# =============================================================================
# SmartApply — Application Package
# =============================================================================
# Autonomous internship application agent powered by Cerebras + Playwright.
# =============================================================================

"""
SmartApply — Autonomous Internship Auto-Applier

Powered by Cerebras API (gpt-oss-120b) with Playwright browser automation.
Architecture:
- FastAPI REST API for orchestration
- Cerebras API with function-calling for autonomous LLM reasoning
- Playwright for headless browser automation
- SQLite for persistent memory & job tracking
"""

__version__ = "0.4.0"
__author__ = "SmartApply Team"
