"""
Instagram scraping tool for the Kirin platform MCP Server.
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime
from agents.pure_functions import build_mcp_error, compute_instagram_inativo
from tools.browser_utils import (
    navigate_to_url,
    extract_text,
    extract_all_attributes,
    extract_text_multiple,
    rate_limit_wait,
    stealth_session,
)


async def get_instagram_profile(username: str) -> Dict[str, Any]:
    """Get Instagram profile information with fallbacks."""
    await rate_limit_wait()

    result = await _scrape_instagram_profile(username)

    if result.get("instagram_status") == "bloqueado":
        decoy_user = os.getenv("INSTAGRAM_DECOY_USER")
        decoy_pass = os.getenv("INSTAGRAM_DECOY_PASS")
        if decoy_user and decoy_pass:
            decoy_result = await _scrape_instagram_profile(username, decoy_user, decoy_pass)
            if decoy_result.get("instagram_status") != "bloqueado":
                return decoy_result

        third_party_url = os.getenv("INSTAGRAM_THIRD_PARTY_API_URL")
        if third_party_url:
            api_result = await _get_instagram_via_api(username, third_party_url)
            if api_result and api_result.get("instagram_status") != "bloqueado":
                return api_result

    return result


async def _scrape_instagram_profile(
    username: str, user: str = None, password: str = None
) -> Dict[str, Any]:
    """Scrape Instagram profile, optionally after logging in.

    Args:
        username: Instagram username to scrape
        user: Optional login username (triggers login flow)
        password: Optional login password
    """
    profile_url = f"https://www.instagram.com/{username}/"

    async with stealth_session() as (browser, page):
        if user and password:
            login_ok = await _login_if_needed(page, user, password)
            if not login_ok:
                return _blocked_result()

        if not await navigate_to_url(page, profile_url):
            return _not_found_result(username)

        page_content = await page.content()

        for indicator in [
            "Sorry, this page isn't available.",
            "The link you followed may be broken.",
            "User may have been removed",
        ]:
            if indicator in page_content:
                return _not_found_result(username)

        if await page.query_selector('h2:has-text("This Account is Private")'):
            return {
                "followers": 0,
                "post_count": 0,
                "last_post_date": None,
                "recent_images": [],
                "instagram_status": "privado",
            }

        # Only check blocking indicators on non-login path
        if not user:
            for indicator in [
                "Please wait a few minutes before you try again.",
                "We restrict certain activity to protect our community",
                "Try again later",
            ]:
                if indicator in page_content:
                    return _blocked_result()

        followers = await _extract_followers(page)
        post_count = await _extract_post_count(page)
        recent_images, last_post_date = await _extract_posts_and_date(page)
        instagram_inativo = bool(last_post_date and compute_instagram_inativo(last_post_date))

        result = {
            "followers": followers,
            "post_count": post_count,
            "last_post_date": last_post_date,
            "recent_images": recent_images[:6],
            "instagram_inativo": instagram_inativo,
        }

        if not recent_images and post_count == 0:
            result["instagram_status"] = "sem_publicacoes"
        elif last_post_date is None:
            result["instagram_status"] = "data_indisponivel"
        else:
            result["instagram_status"] = "ativo"

        return result


async def _login_if_needed(page, username: str, password: str) -> bool:
    """Log in to Instagram. Returns True if successful or not needed."""
    if not username or not password:
        return True
    try:
        await page.goto("https://www.instagram.com/accounts/login/", timeout=30000)
        await page.wait_for_load_state("networkidle")
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)
        home_icon = await page.query_selector('svg[aria-label="Home"]')
        return home_icon is not None
    except Exception:
        return False


async def _extract_followers(page) -> int:
    """Extract followers count from profile page."""
    import re
    text = await extract_text_multiple(
        page,
        'ul li:nth-child(2) span',
        'header section ul li:nth-child(2) span',
        'meta[property="og:description"]',
    )
    if text:
        match = re.search(r'[\d,.]+', text.replace(',', ''))
        if match:
            try:
                return int(float(match.group()))
            except ValueError:
                pass
    return 0


async def _extract_post_count(page) -> int:
    """Extract post count from profile page."""
    import re
    text = await extract_text_multiple(
        page,
        'ul li:nth-child(1) span',
        'header section ul li:nth-child(1) span',
    )
    if text:
        match = re.search(r'[\d,.]+', text.replace(',', ''))
        if match:
            try:
                return int(float(match.group()))
            except ValueError:
                pass
    return 0


async def _extract_posts_and_date(page) -> tuple[list, Optional[str]]:
    """Extract recent post images and last post date."""
    recent_images = []
    last_post_date = None

    post_links = await extract_all_attributes(page, 'a[href*="/p/"]', 'href')

    for post_link in post_links[:6]:
        post_url = f"https://www.instagram.com{post_link}" if post_link.startswith('/') else post_link
        try:
            post_element = await page.query_selector(f'a[href="{post_link}"]')
            if post_element:
                img_element = await post_element.query_selector('img')
                if img_element:
                    img_url = await img_element.get_attribute('src')
                    if img_url:
                        recent_images.append(img_url)
        except Exception:
            pass

    if post_links:
        try:
            first_post_link = post_links[0]
            first_post_url = f"https://www.instagram.com{first_post_link}" if first_post_link.startswith('/') else first_post_link
            await page.goto(first_post_url, timeout=15000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
            date_element = await page.query_selector('time')
            if date_element:
                datetime_str = await date_element.get_attribute('datetime')
                if datetime_str:
                    last_post_date = datetime_str
        except Exception:
            pass

    return recent_images, last_post_date


def _blocked_result() -> Dict[str, Any]:
    return {
        "followers": 0, "post_count": 0, "last_post_date": None,
        "recent_images": [], "instagram_status": "bloqueado",
    }


def _not_found_result(username: str) -> Dict[str, Any]:
    return {
        "followers": 0, "post_count": 0, "last_post_date": None,
        "recent_images": [], "instagram_status": "não encontrado",
    }


async def _get_instagram_via_api(username: str, api_url: str) -> Optional[Dict[str, Any]]:
    """Get Instagram profile via third-party API."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{api_url.rstrip('/')}/{username}")
            if response.status_code == 200:
                data = response.json()
                last_post_date = data.get("last_post_date")
                recent_images = data.get("recent_images", [])[:6]
                instagram_inativo = bool(last_post_date and compute_instagram_inativo(last_post_date))
                return {
                    "followers": data.get("followers", 0),
                    "post_count": data.get("post_count", 0),
                    "last_post_date": last_post_date,
                    "recent_images": recent_images,
                    "instagram_inativo": instagram_inativo,
                    "instagram_status": "ativo" if recent_images or data.get("post_count", 0) > 0 else "sem_publicacoes",
                }
            elif response.status_code == 404:
                return _not_found_result(username)
            else:
                return _blocked_result()
    except Exception:
        return _blocked_result()
