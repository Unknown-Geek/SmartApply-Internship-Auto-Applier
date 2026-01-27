# =============================================================================
# SmartApply Web Agent - Web Agent Implementation
# =============================================================================
# This module provides the browser-use web agent with Gemini 2.0 Flash LLM.
# Designed for headless operation on OCI Ubuntu VMs.
# =============================================================================

import asyncio
from typing import Optional
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig

from app.config import get_settings


@dataclass
class WebAgent:
    """
    Web automation agent using browser-use with Gemini 2.0 Flash.
    
    This agent can perform web browsing tasks autonomously, such as:
    - Navigating to websites
    - Filling forms
    - Clicking buttons
    - Extracting information
    
    Attributes:
        task: The task description for the agent to execute
        llm: The language model instance (Gemini 2.0 Flash)
        browser: The browser instance for web automation
        agent: The browser-use agent instance
    
    Example:
        agent = await create_web_agent("Search for Python tutorials")
        result = await agent.run()
        await agent.close()
    """
    
    task: str
    llm: ChatGoogleGenerativeAI = field(init=False)
    browser: Optional[Browser] = field(default=None, init=False)
    agent: Optional[Agent] = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    
    async def initialize(self) -> None:
        """
        Initialize the web agent with LLM and browser.
        
        This method sets up:
        1. Gemini 2.0 Flash LLM via langchain-google-genai
        2. Playwright browser in headless mode
        3. browser-use Agent combining both
        """
        if self._initialized:
            return
        
        settings = get_settings()
        
        # ---------------------------------------------------------------------
        # Step 1: Initialize Gemini 2.0 Flash LLM
        # ---------------------------------------------------------------------
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",  # Gemini 2.0 Flash model
            google_api_key=settings.google_api_key,
            temperature=0.7,  # Balanced creativity/consistency
            convert_system_message_to_human=True,
        )
        
        # ---------------------------------------------------------------------
        # Step 2: Configure Browser for Headless Operation
        # ---------------------------------------------------------------------
        browser_config = BrowserConfig(
            headless=settings.headless,  # True for server deployment
            disable_security=False,       # Keep security enabled
        )
        
        self.browser = Browser(config=browser_config)
        
        # ---------------------------------------------------------------------
        # Step 3: Create browser-use Agent
        # ---------------------------------------------------------------------
        self.agent = Agent(
            task=self.task,
            llm=self.llm,
            browser=self.browser,
        )
        
        self._initialized = True
    
    async def run(self) -> str:
        """
        Execute the web agent task.
        
        Returns:
            str: The result or output from the agent's task execution
        
        Raises:
            RuntimeError: If agent is not initialized
        """
        if not self._initialized:
            await self.initialize()
        
        # Run the agent and get result
        result = await self.agent.run()
        return result
    
    async def close(self) -> None:
        """
        Clean up resources by closing the browser.
        
        Always call this method when done with the agent to prevent
        resource leaks, especially on long-running servers.
        """
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.agent = None
            self._initialized = False


async def create_web_agent(task: str) -> WebAgent:
    """
    Factory function to create and initialize a WebAgent.
    
    This is the recommended way to create a WebAgent instance.
    
    Args:
        task: Description of the task for the agent to perform
        
    Returns:
        WebAgent: An initialized web agent ready to run
        
    Example:
        async with create_web_agent("Find the latest news") as agent:
            result = await agent.run()
            print(result)
    """
    agent = WebAgent(task=task)
    await agent.initialize()
    return agent


# =============================================================================
# Context Manager Support (Optional Enhancement)
# =============================================================================
class WebAgentContext:
    """
    Async context manager for WebAgent to ensure proper cleanup.
    
    Example:
        async with WebAgentContext("Search for Python docs") as agent:
            result = await agent.run()
    """
    
    def __init__(self, task: str):
        self.task = task
        self.agent: Optional[WebAgent] = None
    
    async def __aenter__(self) -> WebAgent:
        self.agent = await create_web_agent(self.task)
        return self.agent
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.agent:
            await self.agent.close()
