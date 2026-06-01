"""
CloakBrowser wrapper for the Kirin MCP Server.

v7.1: CloakBrowser wrapper (stealth Chromium)
v7.2: MCP Server integration
v7.3: Seed management
"""
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloakbrowser"))

try:
    from cloakbrowser import launch, launch_async
    from cloakbrowser.config import CHROMIUM_VERSION
    CLOAKBROWSER_AVAILABLE = True
except ImportError:
    CLOAKBROWSER_AVAILABLE = False

from agents.seeds.manager import SeedManager, SeedEntry

# ── Browser Launch Wrapper ─────────────────────────────────────────────────

class CloakBrowserWrapper:
    """Wrapper around CloakBrowser with seed-based proxy rotation."""

    def __init__(self, seed_manager: Optional[SeedManager] = None):
        self.seed_manager = seed_manager or SeedManager()
        self._browser = None

    @property
    def available(self) -> bool:
        return CLOAKBROWSER_AVAILABLE

    def get_browser(self, proxy_url: Optional[str] = None) -> Any:
        """Launch browser with optional proxy. Returns Playwright Browser."""
        if not CLOAKBROWSER_AVAILABLE:
            raise RuntimeError(
                "CloakBrowser not available. Install: "
                "pip install -e ./cloakbrowser"
            )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("Cannot launch sync browser from async context")
        except RuntimeError:
            pass

        proxy_settings = None
        if proxy_url:
            if isinstance(proxy_url, str) and "@" in proxy_url:
                scheme, rest = proxy_url.split("://", 1)
                auth, host_port = rest.split("@", 1)
                username, password = auth.split(":", 1)
                proxy_settings = {
                    "server": f"{scheme}://{host_port}",
                    "username": username,
                    "password": password,
                }
            else:
                proxy_settings = {"server": proxy_url}

        self._browser = launch(
            headless=True,
            proxy=proxy_settings,
            stealth_args=True,
            timezone="America/Sao_Paulo",
            locale="pt-BR",
            geoip=False,
            humanize=True,
            human_preset="default",
        )
        return self._browser

    async def get_browser_async(self, proxy_url: Optional[str] = None) -> Any:
        """Launch browser async with optional proxy."""
        if not CLOAKBROWSER_AVAILABLE:
            raise RuntimeError(
                "CloakBrowser not available. Install: "
                "pip install -e ./cloakbrowser"
            )

        proxy_settings = None
        if proxy_url:
            if isinstance(proxy_url, str) and "@" in proxy_url:
                scheme, rest = proxy_url.split("://", 1)
                auth, host_port = rest.split("@", 1)
                username, password = auth.split(":", 1)
                proxy_settings = {
                    "server": f"{scheme}://{host_port}",
                    "username": username,
                    "password": password,
                }
            else:
                proxy_settings = {"server": proxy_url}

        self._browser = await launch_async(
            headless=True,
            proxy=proxy_settings,
            stealth_args=True,
            timezone="America/Sao_Paulo",
            locale="pt-BR",
            geoip=False,
            humanize=True,
            human_preset="default",
        )
        return self._browser

    def close(self):
        """Close the browser."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

    def new_page(self, proxy_url: Optional[str] = None):
        """Create a new page, optionally with a fresh browser/proxy."""
        if proxy_url or not self._browser:
            self.close()
            self.get_browser(proxy_url)
        return self._browser.new_page()

    async def new_page_async(self, proxy_url: Optional[str] = None):
        """Create a new page async."""
        if proxy_url or not self._browser:
            self.close()
            await self.get_browser_async(proxy_url)
        return self._browser.new_page()

    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy URL from seed manager."""
        return self.seed_manager.get_random_seed().proxy_url


# ── MCP Tool Integration Helpers ───────────────────────────────────────────

async def launch_stealth_page(proxy_url: Optional[str] = None):
    """Launch a stealth browser page. Returns (browser, page, proxy_used).

    Falls back to no proxy if CloakBrowser is unavailable.
    """
    if not CLOAKBROWSER_AVAILABLE:
        return await _launch_fallback_page(proxy_url)

    proxy_settings = None
    if proxy_url:
        if "@" in proxy_url:
            scheme, rest = proxy_url.split("://", 1)
            auth, host_port = rest.split("@", 1)
            username, password = auth.split(":", 1)
            proxy_settings = {
                "server": f"{scheme}://{host_port}",
                "username": username,
                "password": password,
            }
        else:
            proxy_settings = {"server": proxy_url}

    browser = await launch_async(
        headless=True,
        proxy=proxy_settings,
        stealth_args=True,
        timezone="America/Sao_Paulo",
        locale="pt-BR",
        humanize=True,
        human_preset="default",
    )
    page = await browser.new_page()
    return browser, page, proxy_url


async def _launch_fallback_page(proxy_url: Optional[str] = None):
    """Fallback to plain Playwright if CloakBrowser is unavailable."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    launch_args = ["--enable-automation"]
    browser = await pw.chromium.launch(headless=True, args=launch_args)
    page = await browser.new_page()
    return browser, page, proxy_url


async def close_browser(browser):
    """Safely close a browser."""
    try:
        await browser.close()
    except Exception:
        pass
