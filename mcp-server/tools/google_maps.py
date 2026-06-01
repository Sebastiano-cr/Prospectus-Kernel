"""
Google Maps scraping tool for the Kirin platform MCP Server.
"""
from typing import List, Dict, Any
from agents.pure_functions import build_mcp_error
from tools.browser_utils import (
    navigate_to_url,
    extract_text,
    extract_all_attributes,
    query_selector_all_safe,
    rate_limit_wait,
    stealth_session,
)


async def search_google_maps(query: str, location: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search Google Maps for establishments."""
    await rate_limit_wait()

    search_query = f"{query} {location}".strip()
    search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

    async with stealth_session() as (browser, page):
        # Google Maps needs domcontentloaded — continuous background requests prevent networkidle
        if not await navigate_to_url(page, search_url, wait_state="domcontentloaded"):
            return build_mcp_error(
                error_code="NAVIGATION_FAILED",
                error_message="Failed to navigate to Google Maps",
                retry_after=10,
            )

        await page.wait_for_timeout(8000)

        selectors = [
            "div.Nv2PK",
            "a.hfpxzc",
            "a[data-item-id]",
            "div[jsaction] > a",
        ]

        elements, selector_used = await query_selector_all_safe(page, selectors)
        if not elements:
            return []

        establishments = []
        processed_place_ids = set()
        max_elements = min(len(elements), limit * 2)

        for i in range(min(max_elements, len(elements))):
            if len(establishments) >= limit:
                break
            try:
                element = elements[i]

                if selector_used == "a.hfpxzc":
                    place_url = await element.get_attribute("href")
                else:
                    link_element = await element.query_selector("a")
                    place_url = await link_element.get_attribute("href") if link_element else None

                if not place_url:
                    continue

                place_id = None
                if "/place/" in place_url:
                    place_id = place_url.split("/place/")[1].split("/")[0]
                elif "cid=" in place_url:
                    place_id = place_url.split("cid=")[1].split("&")[0]

                if place_id and place_id in processed_place_ids:
                    continue
                if place_id:
                    processed_place_ids.add(place_id)

                await element.click()
                await page.wait_for_timeout(2000)

                name = await extract_text(page, "h1.DUwDvf") or await extract_text(page, "h1")
                address = await extract_text(page, "button[data-item-id='address']") \
                          or await extract_text(page, "span.LrzXr")
                phone = await extract_text(page, "button[data-item-id^='phone:tel']") \
                        or await extract_text(page, "span.LrzXr.zdqRlf")

                rating_text = await extract_text(page, "span.MW4etd")
                rating = None
                if rating_text:
                    try:
                        rating = float(rating_text.replace(",", "."))
                    except ValueError:
                        pass

                if name:
                    establishments.append({
                        "name": name.strip(),
                        "address": address.strip() if address else None,
                        "phone": phone.strip() if phone else None,
                        "rating": rating,
                        "google_maps_url": place_url,
                    })
            except Exception:
                continue

        return establishments
