# =============================================================================
# SmartApply — Telegram Bot
# =============================================================================
# Telegram bot for human-in-the-loop interaction with the SmartApply agent.
#
# Features:
# - Send a URL → agent starts auto-applying
# - Agent asks questions when stuck → shows up in Telegram
# - User replies → agent continues
# - Status updates from agent → Telegram notifications
#
# Uses python-telegram-bot (v21+) in polling mode alongside FastAPI.
# =============================================================================

import asyncio
import logging
import re
import httpx
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.agent.human_loop import HumanLoop
from app.agent.orchestrator import SmartApplyOrchestrator
from app.config import get_settings
from app.db.database import get_stats, get_all_profile

logger = logging.getLogger("smartapply.telegram")

# URL regex for detecting application links
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)


class SmartApplyBot:
    """
    Telegram bot for SmartApply — human-in-the-loop agent interaction.

    Usage:
        bot = SmartApplyBot(token="...", authorized_chat_id="123456")
        await bot.start()   # starts polling in the background
        ...
        await bot.stop()
    """

    def __init__(self, token: str, authorized_chat_id: str):
        self.token = token
        self.authorized_chat_id = str(authorized_chat_id)
        self.app: Optional[Application] = None
        self.human_loop: Optional[HumanLoop] = None
        self._running = False
        self._active_task: Optional[asyncio.Task] = None

        # Create the HumanLoop bridge, wiring up Telegram send functions
        self.human_loop = HumanLoop(
            notify_fn=self._send_notification,
            ask_fn=self._send_question,
            timeout=300,  # 5 min for user to reply
        )

    def _is_authorized(self, update: Update) -> bool:
        """Check if the message comes from the authorized user."""
        chat_id = str(update.effective_chat.id)
        return chat_id == self.authorized_chat_id

    async def _send_notification(self, message: str) -> None:
        """Send a notification message to the authorized user."""
        if self.app and self.app.bot:
            await self.app.bot.send_message(
                chat_id=self.authorized_chat_id,
                text=message,
                parse_mode="Markdown",
            )

    async def _send_question(self, question: str) -> None:
        """Send a question to the authorized user (agent is waiting for reply)."""
        if self.app and self.app.bot:
            await self.app.bot.send_message(
                chat_id=self.authorized_chat_id,
                text=f"❓ *Agent needs your input:*\n\n{question}\n\n_Reply to this message with your answer._",
                parse_mode="Markdown",
            )

    # =========================================================================
    # Command Handlers
    # =========================================================================

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized. Your chat ID is not registered.")
            return

        await update.message.reply_text(
            "👋 *Welcome to SmartApply!*\n\n"
            "I'm your autonomous internship application assistant.\n\n"
            "*How to use:*\n"
            "• Send me an application URL and I'll start applying automatically\n"
            "• I'll ask you questions when I need information\n"
            "• I'll notify you of progress and results\n\n"
            "*Commands:*\n"
            "/status — Agent status & stats\n"
            "/profile — View your stored profile\n"
            "/cancel — Cancel the current task\n"
            "/help — Show this help message",
            parse_mode="Markdown",
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self._is_authorized(update):
            return

        stats = get_stats()
        settings = get_settings()

        task_status = "🔄 Working..." if self._active_task and not self._active_task.done() else "💤 Idle"
        waiting = "⏳ Waiting for your reply" if self.human_loop.is_waiting else ""

        msg = (
            f"*SmartApply Status*\n\n"
            f"🤖 Agent: {task_status}\n"
            f"{waiting}\n"
            f"🧠 Model: `{settings.cerebras_model}`\n\n"
            f"📊 *Stats:*\n"
            f"• Jobs found: {stats.get('total_jobs', 0)}\n"
            f"• Applications: {stats.get('total_applications', 0)}\n"
            f"• Sessions: {stats.get('total_sessions', 0)}\n"
            f"• Memory facts: {stats.get('total_memory', 0)}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command."""
        if not self._is_authorized(update):
            return

        profile = get_all_profile()
        if not profile:
            await update.message.reply_text(
                "📋 No profile stored yet.\n\n"
                "Use the API endpoint `POST /profile/ingest` to upload your resume."
            )
            return

        lines = []
        for key, value in profile.items():
            val_str = str(value)
            # Escape HTML characters first
            val_str = val_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(val_str) > 100:
                val_str = val_str[:100] + "..."
            lines.append(f"• <b>{key}:</b> {val_str}")

        # Send in chunks splitting on line boundaries (not mid-HTML-tag)
        chunks = []
        current_chunk = "<b>Your Profile:</b>\n"
        for line in lines:
            if len(current_chunk) + len(line) + 1 > 3900:
                chunks.append(current_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
        if current_chunk.strip():
            chunks.append(current_chunk)

        for chunk in chunks:
            await update.message.reply_text(chunk.strip(), parse_mode="HTML")

    async def _cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command — cancel the current agent task."""
        if not self._is_authorized(update):
            return

        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._active_task = None
            await update.message.reply_text("❌ Current task cancelled.")
        else:
            await update.message.reply_text("💤 No active task to cancel.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await self._cmd_start(update, context)

    async def _cmd_apply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /apply <url> command for immediate execution."""
        if not self._is_authorized(update):
            return

        if not context.args:
            await update.message.reply_text("Usage: /apply <url>")
            return

        url = context.args[0]
        if not URL_PATTERN.match(url):
            await update.message.reply_text("Invalid URL format.")
            return

        if self._active_task and not self._active_task.done():
            await update.message.reply_text("⚠️ An agent task is already running. Use /cancel to stop it first.")
            return

        await update.message.reply_text(
            f"🚀 *Forcing immediate run!* Starting application process for:\n`{url}`",
            parse_mode="Markdown",
        )

        self._active_task = asyncio.create_task(self._run_application(url))

    # =========================================================================
    # Message Handlers
    # =========================================================================

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages (URLs or answers to agent questions)."""
        if not self._is_authorized(update):
            return

        text = update.message.text.strip()

        # Check if the agent is waiting for an answer
        if self.human_loop.is_waiting:
            delivered = self.human_loop.provide_answer(text)
            if delivered:
                await update.message.reply_text("✅ Got it! Passing your answer to the agent...")
                return
            else:
                await update.message.reply_text("⚠️ No pending question. Your message was not delivered.")

        # Check if the message contains a URL
        urls = URL_PATTERN.findall(text)
        if urls:
            url = urls[0]  # Use the first URL found
            
            # Try to extract company and title from the specific forwarded format
            # Format: Title: ..., Company: ..., ... Apply Link: http...
            company = ""
            title = ""
            
            title_match = re.search(r"Title:\s*(.+)", text, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
                
            company_match = re.search(r"Company:\s*(.+)", text, re.IGNORECASE)
            if company_match:
                company = company_match.group(1).strip()
            
            # Check if we should queue the URL instead of running immediately
            settings = get_settings()
            if settings.smartapply_queue_webhook:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            settings.smartapply_queue_webhook,
                            json={
                                "url": url, 
                                "source": "Telegram Bot",
                                "company": company,
                                "title": title
                            },
                            timeout=10.0
                        )
                        if resp.status_code == 200:
                            details = f"URL: `{url}`\n"
                            if title and company:
                                details = f"📝 *{title}* at *{company}*\n" + details
                                
                            await update.message.reply_text(
                                f"📥 *Added to Queue!*\n\n"
                                f"{details}"
                                f"The batch processor will handle this application later.\n"
                                f"_Use /apply <url> if you want to force an immediate run._",
                                parse_mode="Markdown"
                            )
                        else:
                            await update.message.reply_text(f"❌ Failed to queue URL (Status: {resp.status_code})")
                except Exception as e:
                    logger.exception("Queue webhook error")
                    await update.message.reply_text(f"❌ Error contacting queue webhook: {e}")
                return

            if self._active_task and not self._active_task.done():
                await update.message.reply_text(
                    "⚠️ An agent task is already running. Use /cancel to stop it first."
                )
                return

            await update.message.reply_text(
                f"🔍 *Got it!* Starting application process for:\n`{url}`\n\n"
                f"I'll notify you of progress...",
                parse_mode="Markdown",
            )

            # Launch the agent task in the background
            self._active_task = asyncio.create_task(
                self._run_application(url)
            )
            return

        # Default: unknown message
        await update.message.reply_text(
            "🤔 Send me an *application URL* to auto-apply, or use /help for commands.",
            parse_mode="Markdown",
        )

    async def _run_application(self, url: str) -> None:
        """Run the application process for a URL (background task)."""
        try:
            orchestrator = SmartApplyOrchestrator(
                human_loop=self.human_loop,
            )
            result = await orchestrator.apply_to_url(url)
            logger.info("Application result for %s: %s", url, result)
        except asyncio.CancelledError:
            logger.info("Application task cancelled for %s", url)
            await self._send_notification("❌ Task was cancelled.")
        except Exception as e:
            logger.exception("Error running application for %s", url)
            await self._send_notification(f"❌ Error: {str(e)}")
        finally:
            self._active_task = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start the Telegram bot (polling mode, runs in background)."""
        if self._running:
            logger.warning("Bot already running")
            return

        logger.info("Starting SmartApply Telegram bot...")

        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("profile", self._cmd_profile))
        self.app.add_handler(CommandHandler("apply", self._cmd_apply))
        self.app.add_handler(CommandHandler("cancel", self._cmd_cancel))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Set bot commands (visible in Telegram menu)
        await self.app.bot.set_my_commands([
            BotCommand("start", "Welcome & help"),
            BotCommand("status", "Agent status & stats"),
            BotCommand("profile", "View stored profile"),
            BotCommand("apply", "Force immediate application for a URL"),
            BotCommand("cancel", "Cancel current task"),
            BotCommand("help", "Show help"),
        ])

        # Initialize and start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        self._running = True
        logger.info("Telegram bot started (polling mode)")

        # Notify user that bot is online
        try:
            await self.app.bot.send_message(
                chat_id=self.authorized_chat_id,
                text="🟢 *SmartApply is online!*\nSend me an application URL to get started.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning("Could not send startup message: %s", e)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if not self._running:
            return

        logger.info("Stopping Telegram bot...")

        # Cancel any active task
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()

        if self.app:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

        self._running = False
        logger.info("Telegram bot stopped")


# =============================================================================
# Module-level singleton accessor
# =============================================================================

_bot_instance: Optional[SmartApplyBot] = None


def get_bot() -> Optional[SmartApplyBot]:
    """Get the global bot instance (if initialized)."""
    return _bot_instance


def init_bot(token: str, chat_id: str) -> SmartApplyBot:
    """Initialize the global bot instance."""
    global _bot_instance
    _bot_instance = SmartApplyBot(token=token, authorized_chat_id=chat_id)
    return _bot_instance
