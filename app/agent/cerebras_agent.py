# =============================================================================
# SmartApply — Cerebras Agent with Function-Calling + Playwright
# =============================================================================
# Standalone agent using the OpenAI-compatible Cerebras API (gpt-oss-120b)
# with function-calling to drive a headless Playwright browser.
#
# The agentic loop:
#   1. Send prompt + tool declarations to Cerebras
#   2. Model responds with tool_calls
#   3. We execute them via BrowserManager
#   4. Feed results back to the model
#   5. Repeat until the model returns a text response (done)
# =============================================================================

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from app.agent.browser_manager import BrowserManager
from app.agent.human_loop import HumanLoop
from app.db.database import log_session_start, log_session_end

logger = logging.getLogger("smartapply.agent")


# =============================================================================
# Result dataclass
# =============================================================================

@dataclass
class AgentResult:
    """Structured result from an agent run."""
    session_id: str
    success: bool
    text: str = ""
    error: str = ""
    model: str = ""
    raw: str = ""


# =============================================================================
# Tool Declarations (OpenAI format)
# =============================================================================

BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Navigate the browser to a URL and return the page title and a preview of visible text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to navigate to (include https://)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_page_data",
            "description": "Extract all form fields, buttons, and links from the current page. Use this to understand page structure before filling forms.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_text",
            "description": "Get the full visible text content of the current page (up to 5000 characters).",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {"type": "integer", "description": "Maximum characters to return (default 5000)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_form",
            "description": "Fill a form input field with a value. Use the CSS selector from extract_page_data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input field (e.g. '#email', 'input[name=\"name\"]')"},
                    "value": {"type": "string", "description": "The value to fill in"},
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element on the page (button, link, etc.) by CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "select_option",
            "description": "Select an option from a dropdown/select element by its visible label text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the select element"},
                    "value": {"type": "string", "description": "The visible label text of the option to select"},
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "Upload a file to a file input element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the file input"},
                    "file_path": {"type": "string", "description": "Absolute path to the file to upload"},
                },
                "required": ["selector", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text character-by-character into a focused input. Use when fill_form doesn't work with certain inputs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input"},
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current page. Use to verify visual state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for",
            "description": "Wait for an element to appear on the page, or wait for a fixed duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to wait for (optional)"},
                    "milliseconds": {"type": "integer", "description": "Milliseconds to wait (optional, use if no selector)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a question when you are missing required information (e.g. GPA, phone number, specific experience details). The user will reply via Telegram. Use this when a form field requires info not in the user profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to ask the user (be specific about what you need)"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_user",
            "description": "Send a status update or notification to the user via Telegram. Use for progress updates, completion notices, or to report issues like CAPTCHAs or login walls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The message to send to the user"},
                },
                "required": ["message"],
            },
        },
    },
]


# =============================================================================
# Cerebras Agent Class
# =============================================================================

class CerebrasAgent:
    """
    Autonomous agent using Cerebras API (OpenAI-compatible) + Playwright browser.

    Usage:
        agent = CerebrasAgent(api_key="...", model="gpt-oss-120b")
        result = await agent.run("Go to example.com and get the page title")
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-oss-120b",
        temperature: float = 0.3,
        base_url: str = "https://api.cerebras.ai/v1",
        headless: bool = True,
        max_turns: int = 25,
        timeout_seconds: int = 600,
        human_loop: Optional[HumanLoop] = None,
    ):
        self.model_name = model
        self.temperature = temperature
        self.headless = headless
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.human_loop = human_loop

        # OpenAI-compatible client pointed at Cerebras
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def run(
        self,
        prompt: str,
        *,
        task_type: str = "general",
        session_id: str = None,
        system_instruction: str = None,
    ) -> AgentResult:
        """
        Run the agent with a prompt. Returns AgentResult.

        The agent will:
        1. Send the prompt to the model with browser tools
        2. Execute any tool calls the model makes
        3. Loop until the model returns a final text answer
        """
        sid = session_id or f"sa-{uuid.uuid4().hex[:12]}"
        log_session_start(sid, task_type, prompt)

        default_system = (
            "You are SmartApply, an autonomous internship application agent. "
            "You have access to a headless browser via the provided tools. "
            "Use browse_url to navigate to websites, extract_page_data to analyze forms, "
            "fill_form/click_element to interact with pages, and take_screenshot to verify state. "
            "Be methodical: navigate → analyze → act → verify. "
            "If you need information not available in the user profile, use ask_user to ask. "
            "Use notify_user to send progress updates (e.g. 'Starting application for X'). "
            "When your task is complete, return a clear summary of what you did and the results."
        )

        # Build initial messages
        messages = [
            {"role": "system", "content": system_instruction or default_system},
            {"role": "user", "content": prompt},
        ]

        async with BrowserManager(headless=self.headless) as browser:
            try:
                result = await asyncio.wait_for(
                    self._agent_loop(messages, browser, sid),
                    timeout=self.timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                log_session_end(sid, "timeout", error="Agent timed out")
                return AgentResult(session_id=sid, success=False, error="Agent timed out", model=self.model_name)
            except Exception as exc:
                logger.exception("Agent error")
                log_session_end(sid, "failed", error=str(exc))
                return AgentResult(session_id=sid, success=False, error=str(exc), model=self.model_name)

    async def _agent_loop(
        self,
        messages: list[dict],
        browser: BrowserManager,
        session_id: str,
    ) -> AgentResult:
        """Core agentic loop: prompt → tool calls → execute → repeat."""

        for turn in range(self.max_turns):
            logger.info("Agent turn %d/%d", turn + 1, self.max_turns)

            # Call the model
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=BROWSER_TOOLS,
                tool_choice="auto",
                temperature=self.temperature,
            )

            choice = response.choices[0]
            message = choice.message

            # If the model wants to call tools
            if message.tool_calls:
                # Append the assistant message (with tool_calls) to history
                messages.append(message.model_dump())

                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    logger.info("Calling tool: %s(%s)", fn_name, json.dumps(fn_args, default=str)[:200])

                    result_data = await self._execute_tool(browser, fn_name, fn_args)

                    logger.info("Tool result: %s", json.dumps(result_data, default=str)[:300])

                    # Append tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result_data, default=str),
                    })
            else:
                # Final text response — no more tool calls
                final_text = message.content or "(empty response)"
                log_session_end(session_id, "completed", result_text=final_text, model_used=self.model_name)
                return AgentResult(
                    session_id=session_id, success=True,
                    text=final_text, model=self.model_name,
                )

            # Check for finish_reason == "stop" with content
            if choice.finish_reason == "stop" and message.content:
                final_text = message.content
                log_session_end(session_id, "completed", result_text=final_text, model_used=self.model_name)
                return AgentResult(
                    session_id=session_id, success=True,
                    text=final_text, model=self.model_name,
                )

        # Exhausted max turns
        final_text = "Max agent turns reached. Task may be incomplete."
        log_session_end(session_id, "completed", result_text=final_text, model_used=self.model_name)
        return AgentResult(
            session_id=session_id, success=True,
            text=final_text, model=self.model_name,
        )

    async def _execute_tool(self, browser: BrowserManager, name: str, args: dict) -> dict:
        """Execute a browser tool by name and return the result."""
        try:
            match name:
                case "browse_url":
                    return await browser.browse_url(args["url"])
                case "extract_page_data":
                    return await browser.extract_page_data()
                case "get_page_text":
                    max_chars = int(args.get("max_chars", 5000))
                    return await browser.get_page_text(max_chars=max_chars)
                case "fill_form":
                    return await browser.fill_form(args["selector"], args["value"])
                case "click_element":
                    return await browser.click_element(args["selector"])
                case "select_option":
                    return await browser.select_option(args["selector"], args["value"])
                case "upload_file":
                    return await browser.upload_file(args["selector"], args["file_path"])
                case "type_text":
                    return await browser.type_text(args["selector"], args["text"])
                case "take_screenshot":
                    result = await browser.take_screenshot()
                    if result.get("success"):
                        return {"success": True, "message": "Screenshot captured successfully."}
                    return result
                case "wait_for":
                    return await browser.wait_for(
                        selector=args.get("selector"),
                        milliseconds=int(args["milliseconds"]) if "milliseconds" in args else None,
                    )
                case "ask_user":
                    if self.human_loop:
                        answer = await self.human_loop.ask(args["question"])
                        return {"success": True, "answer": answer}
                    return {"success": False, "answer": "(No Telegram bot connected — use best judgment or skip)"}
                case "notify_user":
                    if self.human_loop:
                        await self.human_loop.notify(args["message"])
                        return {"success": True, "message": "Notification sent."}
                    return {"success": True, "message": "(No Telegram bot — notification logged only)"}
                case _:
                    return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"success": False, "error": f"Tool execution error: {str(e)}"}
