# =============================================================================
# SmartApply — Human-in-the-Loop Bridge
# =============================================================================
# Async bridge between the Cerebras agent and the Telegram bot.
# When the agent needs user input, it calls ask() which suspends
# until the user replies via Telegram.
# =============================================================================

import asyncio
import logging
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("smartapply.humanloop")


class HumanLoop:
    """
    Async bridge for agent ↔ human communication via Telegram.

    Usage (agent side):
        answer = await human_loop.ask("What is your GPA?")

    Usage (Telegram bot side):
        human_loop.provide_answer("3.8")
    """

    def __init__(
        self,
        notify_fn: Optional[Callable[[str], Awaitable[None]]] = None,
        ask_fn: Optional[Callable[[str], Awaitable[None]]] = None,
        timeout: float = 300,
    ):
        self._notify_fn = notify_fn  # sends a message to Telegram
        self._ask_fn = ask_fn        # sends a question to Telegram
        self._timeout = timeout      # seconds to wait for user reply
        self._pending_future: Optional[asyncio.Future] = None
        self._pending_question: Optional[str] = None

    @property
    def is_waiting(self) -> bool:
        """True if the agent is currently waiting for a user reply."""
        return self._pending_future is not None and not self._pending_future.done()

    @property
    def pending_question(self) -> Optional[str]:
        return self._pending_question

    async def notify(self, message: str) -> None:
        """Send a fire-and-forget notification to the user."""
        logger.info("Notify user: %s", message[:200])
        if self._notify_fn:
            try:
                await self._notify_fn(message)
            except Exception as e:
                logger.warning("Failed to send notification: %s", e)

    async def ask(self, question: str) -> str:
        """
        Ask the user a question and wait for their reply.

        Returns the user's answer as a string.
        Raises TimeoutError if no reply within timeout.
        """
        logger.info("Asking user: %s", question[:200])

        loop = asyncio.get_running_loop()
        self._pending_future = loop.create_future()
        self._pending_question = question

        # Send the question to the user via Telegram
        if self._ask_fn:
            try:
                await self._ask_fn(question)
            except Exception as e:
                logger.warning("Failed to send question: %s", e)
                self._pending_future = None
                self._pending_question = None
                return f"(Could not reach user: {e})"

        # Wait for the answer
        try:
            answer = await asyncio.wait_for(self._pending_future, timeout=self._timeout)
            logger.info("User answered: %s", str(answer)[:200])
            return str(answer)
        except asyncio.TimeoutError:
            logger.warning("User did not reply within %ds", self._timeout)
            return "(User did not reply in time — please use best judgment or skip this field)"
        finally:
            self._pending_future = None
            self._pending_question = None

    def provide_answer(self, answer: str) -> bool:
        """
        Called by the Telegram bot when the user replies.

        Returns True if the answer was delivered, False if no pending question.
        """
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_result(answer)
            return True
        return False
