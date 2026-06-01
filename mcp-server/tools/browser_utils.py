"""
Shared browser utilities for MCP Server scraping tools.
Eliminates duplicated helpers between google_maps.py and instagram.py.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, List, Optional

from playwright.async_api import Page

# ── Rate Limiting ──────────────────────────────────────────────────────────

_last_request_time: float = 0
_MIN_INTERVAL: float = 2.0


async def rate_limit_wait(interval: float = _MIN_INTERVAL) -> None:
    """Wait if needed to respect rate limiting interval."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < interval:
        await asyncio.sleep(interval - elapsed)
    _last_request_time = time.time()


# ── Browser Lifecycle ──────────────────────────────────────────────────────

@asynccontextmanager
async def stealth_session():
    """Context manager for CloakBrowser with automatic cleanup.

    Usage:
        async with stealth_session() as (browser, page):
            await page.goto("https://example.com")
    """
    from cloak_browser import launch_stealth_page, close_browser

    browser = None
    page = None
    try:
        browser, page, _ = await launch_stealth_page()
        yield browser, page
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if browser:
            await close_browser(browser)


# ── Page Helpers ───────────────────────────────────────────────────────────

async def navigate_to_url(
    page: Page, url: str, timeout: int = 30000, wait_state: str = "networkidle"
) -> bool:
    """Navigate to a URL and wait for page to load.

    Args:
        page: Playwright page object
        url: URL to navigate to
        timeout: Timeout in milliseconds
        wait_state: Load state to wait for ("domcontentloaded" or "networkidle")

    Returns:
        True if navigation successful, False otherwise
    """
    try:
        await page.goto(url, timeout=timeout)
        await page.wait_for_load_state(wait_state)
        return True
    except Exception:
        return False


async def extract_text(page: Page, selector: str) -> Optional[str]:
    """Extract text content from an element."""
    try:
        element = await page.query_selector(selector)
        if element:
            return await element.inner_text()
        return None
    except Exception:
        return None


async def extract_attribute(page: Page, selector: str, attribute: str) -> Optional[str]:
    """Extract attribute value from an element."""
    try:
        element = await page.query_selector(selector)
        if element:
            return await element.get_attribute(attribute)
        return None
    except Exception:
        return None


async def extract_all_attributes(page: Page, selector: str, attribute: str) -> List[str]:
    """Extract attribute values from all matching elements."""
    try:
        elements = await page.query_selector_all(selector)
        values = []
        for element in elements:
            value = await element.get_attribute(attribute)
            if value:
                values.append(value)
        return values
    except Exception:
        return []


async def take_screenshot(page: Page, path: str = None) -> Optional[bytes]:
    """Take a screenshot of the page."""
    try:
        if path:
            await page.screenshot(path=path)
            return None
        else:
            return await page.screenshot()
    except Exception:
        return None


async def query_selector_all_safe(page: Page, selectors: List[str]) -> tuple[List[Any], Optional[str]]:
    """Try multiple selectors, return elements from first match.

    Returns:
        (elements, selector_used) or ([], None) if none match
    """
    for selector in selectors:
        try:
            found = await page.query_selector_all(selector)
            if found:
                return found, selector
        except Exception:
            continue
    return [], None


async def extract_text_multiple(page: Page, *selectors: str) -> Optional[str]:
    """Try multiple selectors for text, return first non-None result."""
    for selector in selectors:
        text = await extract_text(page, selector)
        if text:
            return text
    return None
