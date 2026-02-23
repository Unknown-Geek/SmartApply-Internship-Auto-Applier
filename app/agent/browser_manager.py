# =============================================================================
# SmartApply — Playwright Browser Manager
# =============================================================================
# Headless Chromium browser automation for the Gemini agent.
# No Chrome extension required — fully autonomous.
#
# Exposes high-level methods that map 1:1 to Gemini function-calling tools:
#   browse_url, fill_form, click_element, select_option, upload_file,
#   take_screenshot, extract_page_data, get_page_text
# =============================================================================

import asyncio
import base64
import logging
from typing import Optional
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)

logger = logging.getLogger("smartapply.browser")


class BrowserManager:
    """
    Manages a headless Chromium browser for the Gemini agent.

    Usage:
        async with BrowserManager() as bm:
            await bm.browse_url("https://example.com")
            text = await bm.get_page_text()
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def launch(self) -> None:
        """Launch the headless browser."""
        if self._browser:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        logger.info("Browser launched (headless=%s)", self.headless)

    async def close(self) -> None:
        """Close all browser resources."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._browser = None
            self._playwright = None
            self._page = None
            self._context = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    # =========================================================================
    # Tool Methods (called by Gemini via function-calling)
    # =========================================================================

    async def browse_url(self, url: str) -> dict:
        """Navigate to a URL and return page info."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            # Give dynamic pages a moment
            await asyncio.sleep(1)
            title = await self.page.title()
            current_url = self.page.url
            # Get a text summary (first 3000 chars)
            text = await self._get_visible_text(max_chars=3000)
            return {
                "success": True,
                "title": title,
                "url": current_url,
                "text_preview": text,
            }
        except PlaywrightTimeout:
            return {"success": False, "error": f"Timeout loading {url}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fill_form(self, selector: str, value: str) -> dict:
        """Fill a form field identified by CSS selector with a value."""
        try:
            el = await self.page.wait_for_selector(selector, timeout=self.timeout_ms)
            if not el:
                return {"success": False, "error": f"Element not found: {selector}"}
            await el.fill(value)
            return {"success": True, "selector": selector, "value": value}
        except PlaywrightTimeout:
            return {"success": False, "error": f"Timeout finding: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click_element(self, selector: str) -> dict:
        """Click an element identified by CSS selector."""
        try:
            await self.page.click(selector, timeout=self.timeout_ms)
            await asyncio.sleep(0.5)
            return {"success": True, "selector": selector, "current_url": self.page.url}
        except PlaywrightTimeout:
            return {"success": False, "error": f"Timeout clicking: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def select_option(self, selector: str, value: str) -> dict:
        """Select an option from a dropdown by label text."""
        try:
            await self.page.select_option(selector, label=value, timeout=self.timeout_ms)
            return {"success": True, "selector": selector, "selected": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def upload_file(self, selector: str, file_path: str) -> dict:
        """Upload a file to a file input element."""
        try:
            el = await self.page.wait_for_selector(selector, timeout=self.timeout_ms)
            if not el:
                return {"success": False, "error": f"File input not found: {selector}"}
            await el.set_input_files(file_path)
            return {"success": True, "selector": selector, "file": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def take_screenshot(self) -> dict:
        """Take a screenshot and return it as base64."""
        try:
            screenshot_bytes = await self.page.screenshot(full_page=False)
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {"success": True, "screenshot_base64": b64}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract_page_data(self) -> dict:
        """Extract form fields, buttons, and links from the current page."""
        try:
            data = await self.page.evaluate("""
                () => {
                    // Form fields
                    const fields = [];
                    document.querySelectorAll('input, textarea, select').forEach((el, i) => {
                        if (el.type === 'hidden') return;
                        let selector = '';
                        if (el.id) selector = '#' + el.id;
                        else if (el.name) selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                        else selector = `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`;

                        let label = null;
                        if (el.id) {
                            const lbl = document.querySelector(`label[for="${el.id}"]`);
                            if (lbl) label = lbl.textContent.trim();
                        }
                        if (!label && el.closest('label'))
                            label = el.closest('label').textContent.trim();

                        fields.push({
                            type: el.type || el.tagName.toLowerCase(),
                            selector, name: el.name || null,
                            id: el.id || null,
                            placeholder: el.placeholder || null,
                            label, required: el.required || false,
                            value: el.value || null
                        });
                    });

                    // Buttons
                    const buttons = [];
                    document.querySelectorAll('button, input[type="submit"], a[role="button"]').forEach((el, i) => {
                        let selector = '';
                        if (el.id) selector = '#' + el.id;
                        else {
                            const text = (el.textContent || el.value || '').trim();
                            selector = text
                                ? `${el.tagName.toLowerCase()}:has-text("${text.substring(0, 40)}")`
                                : `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`;
                        }
                        buttons.push({
                            type: el.type || 'button',
                            selector,
                            text: (el.textContent || el.value || '').trim().substring(0, 80)
                        });
                    });

                    // Links
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(el => {
                        const text = el.textContent.trim().substring(0, 60);
                        if (text && el.href) {
                            links.push({ text, href: el.href });
                        }
                    });

                    return { fields, buttons, links: links.slice(0, 30) };
                }
            """)
            data["title"] = await self.page.title()
            data["url"] = self.page.url
            return {"success": True, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_text(self, max_chars: int = 5000) -> dict:
        """Get visible text content of the current page."""
        try:
            text = await self._get_visible_text(max_chars=max_chars)
            return {
                "success": True,
                "title": await self.page.title(),
                "url": self.page.url,
                "text": text,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str) -> dict:
        """Type text character-by-character (useful for inputs that reject fill())."""
        try:
            el = await self.page.wait_for_selector(selector, timeout=self.timeout_ms)
            if not el:
                return {"success": False, "error": f"Element not found: {selector}"}
            await el.click()
            await self.page.keyboard.type(text, delay=50)
            return {"success": True, "selector": selector, "typed": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for(self, selector: str = None, milliseconds: int = None) -> dict:
        """Wait for an element to appear or for a fixed duration."""
        try:
            if selector:
                await self.page.wait_for_selector(selector, timeout=self.timeout_ms)
            elif milliseconds:
                await asyncio.sleep(milliseconds / 1000)
            return {"success": True}
        except PlaywrightTimeout:
            return {"success": False, "error": f"Timeout waiting for: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _get_visible_text(self, max_chars: int = 3000) -> str:
        """Extract visible text from the page body."""
        text = await self.page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT,
                    { acceptNode: n => {
                        const p = n.parentElement;
                        if (!p) return NodeFilter.FILTER_REJECT;
                        const tag = p.tagName;
                        if (['SCRIPT','STYLE','NOSCRIPT'].includes(tag)) return NodeFilter.FILTER_REJECT;
                        const s = getComputedStyle(p);
                        if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                        return NodeFilter.FILTER_ACCEPT;
                    }}
                );
                const parts = [];
                let total = 0;
                while (walker.nextNode() && total < 10000) {
                    const t = walker.currentNode.textContent.trim();
                    if (t) { parts.push(t); total += t.length; }
                }
                return parts.join(' ');
            }
        """)
        return text[:max_chars] if text else ""
