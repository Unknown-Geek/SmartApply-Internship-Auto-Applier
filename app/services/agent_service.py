# =============================================================================
# SmartApply Web Agent - Agent Service (Execution Engine)
# =============================================================================
# A pure execution engine for browser automation with two main endpoints:
#   POST /analyze - Captures DOM and returns form fields/buttons
#   POST /execute - Executes a list of specific browser actions
#
# Designed for n8n integration where n8n orchestrates the workflow logic.
# =============================================================================

import asyncio
import base64
import os
from pathlib import Path
from typing import Any, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from app.config import get_settings


# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/agent", tags=["Agent Execution Engine"])


# =============================================================================
# Enums and Models
# =============================================================================

class ActionType(str, Enum):
    """Supported browser action types."""
    TYPE = "type"           # Type text into an input field
    CLICK = "click"         # Click an element
    UPLOAD = "upload"       # Upload a file
    SELECT = "select"       # Select dropdown option
    CHECK = "check"         # Check a checkbox
    UNCHECK = "uncheck"     # Uncheck a checkbox
    WAIT = "wait"           # Wait for element/time
    SCROLL = "scroll"       # Scroll to element
    NAVIGATE = "navigate"   # Navigate to URL
    SCREENSHOT = "screenshot"  # Take screenshot


class BrowserAction(BaseModel):
    """A single browser action to execute."""
    action: ActionType = Field(..., description="Type of action to perform")
    selector: Optional[str] = Field(None, description="CSS selector for the target element")
    text: Optional[str] = Field(None, description="Text to type or value to select")
    file: Optional[str] = Field(None, description="File path for upload actions")
    url: Optional[str] = Field(None, description="URL for navigate actions")
    timeout: int = Field(default=30000, description="Timeout in milliseconds")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {"action": "type", "selector": "#name", "text": "Shravan"},
                {"action": "click", "selector": "button[type='submit']"},
                {"action": "upload", "selector": "input[type='file']", "file": "resume.pdf"},
                {"action": "select", "selector": "#country", "text": "India"},
            ]
        }


# =============================================================================
# Request/Response Models - Analyze
# =============================================================================

class AnalyzeRequest(BaseModel):
    """Request to analyze a page for form elements."""
    url: str = Field(..., description="URL of the page to analyze")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    capture_screenshot: bool = Field(default=True, description="Include screenshot in response")
    timeout: int = Field(default=30000, description="Page load timeout in ms")


class FormField(BaseModel):
    """A detected form field on the page."""
    type: str = Field(..., description="Input type (text, email, file, etc.)")
    selector: str = Field(..., description="CSS selector to target this field")
    name: Optional[str] = Field(None, description="Name attribute")
    id: Optional[str] = Field(None, description="ID attribute")
    placeholder: Optional[str] = Field(None, description="Placeholder text")
    label: Optional[str] = Field(None, description="Associated label text")
    required: bool = Field(default=False, description="Whether field is required")
    value: Optional[str] = Field(None, description="Current value if any")


class ButtonInfo(BaseModel):
    """A detected button on the page."""
    type: str = Field(..., description="Button type (submit, button, etc.)")
    selector: str = Field(..., description="CSS selector to target this button")
    text: str = Field(..., description="Button text content")
    id: Optional[str] = Field(None, description="ID attribute")
    name: Optional[str] = Field(None, description="Name attribute")


class AnalyzeResponse(BaseModel):
    """Response from page analysis."""
    success: bool
    url: str
    title: Optional[str] = None
    fields: list[FormField] = []
    buttons: list[ButtonInfo] = []
    screenshot_base64: Optional[str] = Field(None, description="Base64 encoded screenshot")
    error: Optional[str] = None


# =============================================================================
# Request/Response Models - Execute
# =============================================================================

class ExecuteRequest(BaseModel):
    """Request to execute browser actions."""
    url: str = Field(..., description="Starting URL")
    actions: list[BrowserAction] = Field(..., description="List of actions to execute in order")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    capture_screenshot_on_error: bool = Field(default=True, description="Capture screenshot if action fails")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/apply",
                "actions": [
                    {"action": "type", "selector": "#name", "text": "Shravan"},
                    {"action": "type", "selector": "#email", "text": "shravan@example.com"},
                    {"action": "upload", "selector": "input[type='file']", "file": "resume.pdf"},
                    {"action": "click", "selector": "button[type='submit']"}
                ],
                "headless": True
            }
        }


class ActionResult(BaseModel):
    """Result of a single action execution."""
    action: ActionType
    selector: Optional[str] = None
    success: bool
    error: Optional[str] = None
    screenshot_base64: Optional[str] = None


class ExecuteResponse(BaseModel):
    """Response from action execution."""
    success: bool
    url: str
    actions_executed: int
    actions_total: int
    results: list[ActionResult]
    final_url: Optional[str] = None
    error: Optional[str] = None
    screenshot_base64: Optional[str] = Field(None, description="Final page screenshot")


# =============================================================================
# Browser Helper Functions
# =============================================================================

async def create_browser(headless: bool = True) -> tuple:
    """Create a Playwright browser instance."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    return playwright, browser, page


async def close_browser(playwright, browser):
    """Safely close browser resources."""
    try:
        await browser.close()
        await playwright.stop()
    except Exception:
        pass


async def capture_screenshot(page: Page) -> str:
    """Capture page screenshot and return as base64."""
    screenshot_bytes = await page.screenshot(full_page=False)
    return base64.b64encode(screenshot_bytes).decode("utf-8")


# =============================================================================
# POST /analyze - Page Analysis Endpoint
# =============================================================================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_page(request: AnalyzeRequest):
    """
    Analyze a page and return all form fields and buttons.
    
    This endpoint:
    1. Navigates to the specified URL
    2. Extracts all input fields, textareas, and selects
    3. Identifies all buttons (submit, button elements)
    4. Optionally captures a screenshot
    
    Use this to understand page structure before executing actions.
    """
    playwright = None
    browser = None
    
    try:
        # Create browser
        playwright, browser, page = await create_browser(request.headless)
        
        # Navigate to URL
        await page.goto(request.url, wait_until="networkidle", timeout=request.timeout)
        
        # Get page title
        title = await page.title()
        
        # ---------------------------------------------------------------------
        # Extract Form Fields
        # ---------------------------------------------------------------------
        fields = []
        
        # JavaScript to extract all form fields with their details
        field_data = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, textarea, select');
                
                inputs.forEach((el, index) => {
                    // Skip hidden and submit inputs
                    if (el.type === 'hidden' || el.type === 'submit') return;
                    
                    // Build a unique selector
                    let selector = '';
                    if (el.id) {
                        selector = '#' + el.id;
                    } else if (el.name) {
                        selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                    } else {
                        selector = `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`;
                    }
                    
                    // Find associated label
                    let labelText = null;
                    if (el.id) {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        if (label) labelText = label.textContent.trim();
                    }
                    if (!labelText && el.closest('label')) {
                        labelText = el.closest('label').textContent.trim();
                    }
                    
                    fields.push({
                        type: el.type || el.tagName.toLowerCase(),
                        selector: selector,
                        name: el.name || null,
                        id: el.id || null,
                        placeholder: el.placeholder || null,
                        label: labelText,
                        required: el.required || false,
                        value: el.value || null
                    });
                });
                
                return fields;
            }
        """)
        
        fields = [FormField(**f) for f in field_data]
        
        # ---------------------------------------------------------------------
        # Extract Buttons
        # ---------------------------------------------------------------------
        button_data = await page.evaluate("""
            () => {
                const buttons = [];
                const btnElements = document.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"]');
                
                btnElements.forEach((el, index) => {
                    let selector = '';
                    if (el.id) {
                        selector = '#' + el.id;
                    } else if (el.name) {
                        selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                    } else {
                        // Use text content for better targeting
                        const text = (el.textContent || el.value || '').trim();
                        if (text) {
                            selector = `${el.tagName.toLowerCase()}:has-text("${text}")`;
                        } else {
                            selector = `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`;
                        }
                    }
                    
                    buttons.push({
                        type: el.type || 'button',
                        selector: selector,
                        text: (el.textContent || el.value || '').trim(),
                        id: el.id || null,
                        name: el.name || null
                    });
                });
                
                return buttons;
            }
        """)
        
        buttons = [ButtonInfo(**b) for b in button_data]
        
        # ---------------------------------------------------------------------
        # Capture Screenshot
        # ---------------------------------------------------------------------
        screenshot_b64 = None
        if request.capture_screenshot:
            screenshot_b64 = await capture_screenshot(page)
        
        return AnalyzeResponse(
            success=True,
            url=request.url,
            title=title,
            fields=fields,
            buttons=buttons,
            screenshot_base64=screenshot_b64
        )
        
    except PlaywrightTimeout as e:
        return AnalyzeResponse(
            success=False,
            url=request.url,
            error=f"Page load timeout: {str(e)}"
        )
    except Exception as e:
        return AnalyzeResponse(
            success=False,
            url=request.url,
            error=f"Analysis failed: {str(e)}"
        )
    finally:
        if browser:
            await close_browser(playwright, browser)


# =============================================================================
# POST /execute - Action Execution Endpoint
# =============================================================================

@router.post("/execute", response_model=ExecuteResponse)
async def execute_actions(request: ExecuteRequest):
    """
    Execute a list of browser actions in sequence.
    
    Supported actions:
    - **type**: Type text into an input field
    - **click**: Click an element
    - **upload**: Upload a file
    - **select**: Select a dropdown option
    - **check/uncheck**: Toggle checkboxes
    - **wait**: Wait for element or fixed time
    - **navigate**: Go to a URL
    - **screenshot**: Capture current state
    
    If any action fails, execution stops and returns the exact error.
    """
    playwright = None
    browser = None
    results: list[ActionResult] = []
    settings = get_settings()
    
    try:
        # Create browser
        playwright, browser, page = await create_browser(request.headless)
        
        # Navigate to starting URL
        await page.goto(request.url, wait_until="networkidle", timeout=30000)
        
        # Execute each action in sequence
        for i, action in enumerate(request.actions):
            try:
                result = await execute_single_action(page, action, settings)
                results.append(result)
                
                if not result.success:
                    # Action failed - capture screenshot if enabled
                    if request.capture_screenshot_on_error:
                        result.screenshot_base64 = await capture_screenshot(page)
                    
                    # Stop execution on first failure
                    return ExecuteResponse(
                        success=False,
                        url=request.url,
                        actions_executed=i,
                        actions_total=len(request.actions),
                        results=results,
                        final_url=page.url,
                        error=f"Action {i + 1} failed: {result.error}"
                    )
                    
            except Exception as e:
                # Unexpected error during action
                error_result = ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=False,
                    error=str(e)
                )
                if request.capture_screenshot_on_error:
                    try:
                        error_result.screenshot_base64 = await capture_screenshot(page)
                    except:
                        pass
                results.append(error_result)
                
                return ExecuteResponse(
                    success=False,
                    url=request.url,
                    actions_executed=i,
                    actions_total=len(request.actions),
                    results=results,
                    final_url=page.url,
                    error=f"Action {i + 1} exception: {str(e)}"
                )
        
        # All actions succeeded
        final_screenshot = await capture_screenshot(page)
        
        return ExecuteResponse(
            success=True,
            url=request.url,
            actions_executed=len(request.actions),
            actions_total=len(request.actions),
            results=results,
            final_url=page.url,
            screenshot_base64=final_screenshot
        )
        
    except Exception as e:
        return ExecuteResponse(
            success=False,
            url=request.url,
            actions_executed=0,
            actions_total=len(request.actions),
            results=results,
            error=f"Execution engine error: {str(e)}"
        )
    finally:
        if browser:
            await close_browser(playwright, browser)


async def execute_single_action(page: Page, action: BrowserAction, settings) -> ActionResult:
    """
    Execute a single browser action.
    
    Returns ActionResult with success/error status.
    """
    try:
        match action.action:
            
            # -----------------------------------------------------------------
            # TYPE - Enter text into a field
            # -----------------------------------------------------------------
            case ActionType.TYPE:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for type action"
                    )
                
                element = await page.wait_for_selector(action.selector, timeout=action.timeout)
                await element.fill(action.text or "")
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # CLICK - Click an element
            # -----------------------------------------------------------------
            case ActionType.CLICK:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for click action"
                    )
                
                await page.click(action.selector, timeout=action.timeout)
                # Wait a bit for any navigation/updates
                await asyncio.sleep(0.5)
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # UPLOAD - Upload a file
            # -----------------------------------------------------------------
            case ActionType.UPLOAD:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for upload action"
                    )
                if not action.file:
                    return ActionResult(
                        action=action.action,
                        selector=action.selector,
                        success=False,
                        error="File path required for upload action"
                    )
                
                # Resolve file path
                file_path = Path(action.file)
                if not file_path.is_absolute():
                    # Check in user_data directory first
                    user_data_path = Path("./user_data") / action.file
                    if user_data_path.exists():
                        file_path = user_data_path
                    # Check current directory
                    elif Path(action.file).exists():
                        file_path = Path(action.file)
                    else:
                        return ActionResult(
                            action=action.action,
                            selector=action.selector,
                            success=False,
                            error=f"File not found: {action.file}"
                        )
                
                if not file_path.exists():
                    return ActionResult(
                        action=action.action,
                        selector=action.selector,
                        success=False,
                        error=f"File not found: {file_path}"
                    )
                
                # Upload the file
                file_input = await page.wait_for_selector(action.selector, timeout=action.timeout)
                await file_input.set_input_files(str(file_path.absolute()))
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # SELECT - Select dropdown option
            # -----------------------------------------------------------------
            case ActionType.SELECT:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for select action"
                    )
                
                await page.select_option(action.selector, label=action.text, timeout=action.timeout)
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # CHECK/UNCHECK - Toggle checkbox
            # -----------------------------------------------------------------
            case ActionType.CHECK:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for check action"
                    )
                
                await page.check(action.selector, timeout=action.timeout)
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
                
            case ActionType.UNCHECK:
                if not action.selector:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="Selector required for uncheck action"
                    )
                
                await page.uncheck(action.selector, timeout=action.timeout)
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # WAIT - Wait for element or fixed time
            # -----------------------------------------------------------------
            case ActionType.WAIT:
                if action.selector:
                    await page.wait_for_selector(action.selector, timeout=action.timeout)
                else:
                    # Wait for fixed time (text is milliseconds)
                    wait_ms = int(action.text or "1000")
                    await asyncio.sleep(wait_ms / 1000)
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # SCROLL - Scroll to element
            # -----------------------------------------------------------------
            case ActionType.SCROLL:
                if action.selector:
                    element = await page.wait_for_selector(action.selector, timeout=action.timeout)
                    await element.scroll_into_view_if_needed()
                else:
                    # Scroll by pixel amount (text = pixels)
                    pixels = int(action.text or "500")
                    await page.evaluate(f"window.scrollBy(0, {pixels})")
                
                return ActionResult(
                    action=action.action,
                    selector=action.selector,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # NAVIGATE - Go to URL
            # -----------------------------------------------------------------
            case ActionType.NAVIGATE:
                if not action.url:
                    return ActionResult(
                        action=action.action,
                        success=False,
                        error="URL required for navigate action"
                    )
                
                await page.goto(action.url, wait_until="networkidle", timeout=action.timeout)
                
                return ActionResult(
                    action=action.action,
                    success=True
                )
            
            # -----------------------------------------------------------------
            # SCREENSHOT - Capture current state (returns in result)
            # -----------------------------------------------------------------
            case ActionType.SCREENSHOT:
                screenshot_b64 = await capture_screenshot(page)
                
                return ActionResult(
                    action=action.action,
                    success=True,
                    screenshot_base64=screenshot_b64
                )
            
            # -----------------------------------------------------------------
            # Unknown action
            # -----------------------------------------------------------------
            case _:
                return ActionResult(
                    action=action.action,
                    success=False,
                    error=f"Unknown action type: {action.action}"
                )
                
    except PlaywrightTimeout as e:
        return ActionResult(
            action=action.action,
            selector=action.selector,
            success=False,
            error=f"Timeout waiting for element: {action.selector}"
        )
    except Exception as e:
        return ActionResult(
            action=action.action,
            selector=action.selector,
            success=False,
            error=str(e)
        )
