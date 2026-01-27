# =============================================================================
# SmartApply Web Agent - Browser Agent Runner
# =============================================================================
# This module provides the main browser automation agent for auto-filling
# internship application forms using browser-use and Gemini 2.0 Flash.
#
# Usage:
#   from app.agent.browser_runner import run_browser_agent
#   result = await run_browser_agent("https://example.com/apply", "./data")
# =============================================================================

import asyncio
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig

from app.config import get_settings


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class AgentResult:
    """Result from the browser agent execution."""
    success: bool
    message: str
    url: str
    error: Optional[str] = None


# =============================================================================
# Memory Loading
# =============================================================================

def load_user_context(user_data_path: str) -> str:
    """
    Load user context from a Markdown file.
    
    This file should contain all the information needed to fill forms:
    - Full name, email, phone
    - Education history
    - Work experience
    - Skills
    - Any other relevant profile data
    
    Args:
        user_data_path: Path to directory containing user_context.md
        
    Returns:
        str: Contents of the user_context.md file
        
    Raises:
        FileNotFoundError: If user_context.md doesn't exist
    """
    context_file = Path(user_data_path) / "user_context.md"
    
    if not context_file.exists():
        raise FileNotFoundError(
            f"user_context.md not found at {context_file}. "
            "Please create this file with your profile information."
        )
    
    with open(context_file, "r", encoding="utf-8") as f:
        return f.read()


def get_resume_path(user_data_path: str) -> Optional[str]:
    """
    Get the path to the resume PDF file.
    
    Args:
        user_data_path: Path to directory containing resume.pdf
        
    Returns:
        str or None: Absolute path to resume.pdf if it exists
    """
    resume_file = Path(user_data_path) / "resume.pdf"
    
    if resume_file.exists():
        return str(resume_file.absolute())
    
    # Also check current directory
    cwd_resume = Path.cwd() / "resume.pdf"
    if cwd_resume.exists():
        return str(cwd_resume.absolute())
    
    return None


# =============================================================================
# Main Browser Agent Function
# =============================================================================

async def run_browser_agent(
    target_url: str,
    user_data_path: str,
    headless: bool = True,  # Toggle for local testing (set False to see browser)
) -> AgentResult:
    """
    Run the browser agent to auto-fill an internship application form.
    
    This function:
    1. Loads user context from user_context.md as the agent's 'Memory'
    2. Navigates to the target URL
    3. Finds and fills the application form using AI
    4. Optionally uploads resume.pdf if a file upload is found
    5. Only submits if 100% confident all required fields are filled
    
    Args:
        target_url: The URL of the application form to fill
        user_data_path: Path to directory containing user_context.md and resume.pdf
        headless: Run browser without GUI (True for VM, False for local testing)
        
    Returns:
        AgentResult: Result object with success status and message
        
    Example:
        result = await run_browser_agent(
            target_url="https://company.com/careers/apply",
            user_data_path="./user_data",
            headless=False  # Set True on VM
        )
        if result.success:
            print(f"Application submitted: {result.message}")
        else:
            print(f"Failed: {result.error}")
    """
    settings = get_settings()
    browser = None
    
    try:
        # ---------------------------------------------------------------------
        # Step 1: Load User Context (Memory)
        # ---------------------------------------------------------------------
        try:
            user_context = load_user_context(user_data_path)
        except FileNotFoundError as e:
            return AgentResult(
                success=False,
                message="Failed to load user context",
                url=target_url,
                error=str(e),
            )
        
        # Check for resume
        resume_path = get_resume_path(user_data_path)
        resume_info = f"\nResume file available at: {resume_path}" if resume_path else "\nNo resume.pdf found - skip file uploads if encountered."
        
        # ---------------------------------------------------------------------
        # Step 2: Initialize Gemini 2.0 Flash LLM
        # ---------------------------------------------------------------------
        if not settings.google_api_key:
            return AgentResult(
                success=False,
                message="API key not configured",
                url=target_url,
                error="GOOGLE_API_KEY not set in .env file",
            )
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",  # Gemini 2.0 Flash model
            google_api_key=settings.google_api_key,
            temperature=0.3,  # Lower temperature for more consistent form filling
            convert_system_message_to_human=True,
        )
        
        # ---------------------------------------------------------------------
        # Step 3: Configure Browser (Headless for VM, GUI for local testing)
        # ---------------------------------------------------------------------
        browser_config = BrowserConfig(
            headless=headless,        # Toggle for local testing
            disable_security=False,   # Keep security enabled
        )
        
        browser = Browser(config=browser_config)
        
        # ---------------------------------------------------------------------
        # Step 4: Build the Agent Task with User Context as Memory
        # ---------------------------------------------------------------------
        task = f"""
Go to the target URL: {target_url}

Find the application form on the page.

Use the following user context (Memory) to fill in every field on the form:

--- USER CONTEXT START ---
{user_context}
--- USER CONTEXT END ---

{resume_info}

IMPORTANT INSTRUCTIONS:
1. Navigate to the URL and locate the application form
2. For each form field, find the matching information from the user context
3. Fill in ALL fields you can find information for
4. If you encounter a file upload field for a resume/CV:
   - If resume.pdf path is provided above, upload it
   - If no resume is available, skip the upload
5. ONLY click the submit button if you are 100% confident that ALL required fields are properly filled
6. If you see a CAPTCHA, immediately STOP and return: "ERROR: CAPTCHA detected - manual intervention required"
7. If you get stuck on any step, STOP and return: "ERROR: Got stuck at [describe where you got stuck]"
8. If the form requires fields you don't have information for, STOP and return: "ERROR: Missing required field - [field name]"
9. After successful submission, return: "SUCCESS: Application submitted successfully"

Be careful and methodical. Double-check each field before submission.
"""
        
        # ---------------------------------------------------------------------
        # Step 5: Create and Run the Agent
        # ---------------------------------------------------------------------
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        
        # ---------------------------------------------------------------------
        # Step 6: Parse Result
        # ---------------------------------------------------------------------
        result_str = str(result) if result else ""
        
        # Check for error patterns in the result
        if "ERROR:" in result_str or "CAPTCHA" in result_str.upper():
            return AgentResult(
                success=False,
                message="Agent encountered an issue",
                url=target_url,
                error=result_str,
            )
        
        if "SUCCESS:" in result_str:
            return AgentResult(
                success=True,
                message=result_str,
                url=target_url,
            )
        
        # Default case - assume partial success
        return AgentResult(
            success=True,
            message=f"Agent completed. Result: {result_str}",
            url=target_url,
        )
        
    except Exception as e:
        return AgentResult(
            success=False,
            message="Agent execution failed",
            url=target_url,
            error=str(e),
        )
        
    finally:
        # Always clean up browser resources
        if browser:
            await browser.close()


# =============================================================================
# CLI Entry Point (for testing)
# =============================================================================

async def main():
    """
    CLI entry point for testing the browser agent.
    
    Usage:
        python -m app.agent.browser_runner
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Run SmartApply browser agent")
    parser.add_argument("url", help="Target application URL")
    parser.add_argument(
        "--data-path", 
        default="./user_data",
        help="Path to directory with user_context.md and resume.pdf"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (for local testing)"
    )
    
    args = parser.parse_args()
    
    print(f"🚀 Running browser agent...")
    print(f"   URL: {args.url}")
    print(f"   Data path: {args.data_path}")
    print(f"   Headless: {not args.no_headless}")
    
    result = await run_browser_agent(
        target_url=args.url,
        user_data_path=args.data_path,
        headless=not args.no_headless,
    )
    
    if result.success:
        print(f"✅ {result.message}")
    else:
        print(f"❌ {result.error}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
