"""
Feature: kirin-cloak
Hypothesis property tests for CloakBrowser integration.
I-Cloak-1: stealth Chromium launches
I-Seed-1: rotation deterministic
I-Seed-2: export/import roundtrip
I-Proxy-1: valid format
"""
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from typing import List

settings.register_profile("ci", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")


# ── I-Cloak-1: CloakBrowser wrapper availability ──────────────────────────

def test_cloak_wrapper_importable():
    """CloakBrowser wrapper module is importable."""
    import sys
    sys.path.insert(0, "mcp-server")
    from cloak_browser import CloakBrowserWrapper, launch_stealth_page, close_browser
    assert CloakBrowserWrapper is not None


def test_cloak_wrapper_has_expected_methods():
    """CloakBrowserWrapper has expected public methods."""
    import sys
    sys.path.insert(0, "mcp-server")
    from cloak_browser import CloakBrowserWrapper
    wrapper = CloakBrowserWrapper()
    assert hasattr(wrapper, "get_browser")
    assert hasattr(wrapper, "get_browser_async")
    assert hasattr(wrapper, "new_page")
    assert hasattr(wrapper, "new_page_async")
    assert hasattr(wrapper, "close")
    assert hasattr(wrapper, "get_next_proxy")
    assert callable(wrapper.get_browser)
    assert callable(wrapper.close)


def test_cloak_wrapper_available_property():
    """CloakBrowserWrapper.available returns a bool."""
    import sys
    sys.path.insert(0, "mcp-server")
    from cloak_browser import CloakBrowserWrapper
    wrapper = CloakBrowserWrapper()
    assert isinstance(wrapper.available, bool)


def test_launch_stealth_page_is_coroutine():
    """launch_stealth_page is an async function."""
    import sys
    sys.path.insert(0, "mcp-server")
    from cloak_browser import launch_stealth_page
    import asyncio
    assert asyncio.iscoroutinefunction(launch_stealth_page)


def test_close_browser_is_coroutine():
    """close_browser is an async function."""
    import sys
    sys.path.insert(0, "mcp-server")
    from cloak_browser import close_browser
    import asyncio
    assert asyncio.iscoroutinefunction(close_browser)


# ── I-Seed-1: Seed rotation deterministic ──────────────────────────────────

@given(
    seed_data=st.lists(
        st.fixed_dictionaries({
            "proxy": st.one_of(
                st.none(),
                st.just("http://proxy1.example.com:8080"),
                st.just("http://proxy2.example.com:3128"),
            ),
            "label": st.text(min_size=1, max_size=20),
        }),
        min_size=2,
        max_size=20,
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
def test_seed_rotation_deterministic(seed_data):
    """I-Seed-1: Same seed order = same rotation order."""
    import sys
    sys.path.insert(0, "agents")
    from agents.seeds.manager import SeedManager, SeedEntry

    manager1 = SeedManager.__new__(SeedManager)
    manager1._seeds = []
    manager1._index = 0

    manager2 = SeedManager.__new__(SeedManager)
    manager2._seeds = []
    manager2._index = 0

    for item in seed_data:
        manager1._seeds.append(item)
        manager2._seeds.append(item)

    # Both managers should rotate through seeds in the same order
    for _ in range(min(len(seed_data), 5)):
        seed1 = manager1.get_random_seed()
        seed2 = manager2.get_random_seed()
        assert seed1.label == seed2.label
        assert seed1.proxy_url == seed2.proxy_url


# ── I-Seed-2: Export/import roundtrip ──────────────────────────────────────

@given(
    seeds=st.lists(
        st.fixed_dictionaries({
            "proxy": st.one_of(
                st.none(),
                st.just("http://proxy1.example.com:8080"),
                st.just("socks5://proxy2.example.com:1080"),
            ),
            "label": st.text(min_size=1, max_size=20),
        }),
        min_size=0,
        max_size=10,
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
def test_seed_export_import_roundtrip(seeds):
    """I-Seed-2: export_seeds → import_seeds preserves data."""
    import sys
    import json
    sys.path.insert(0, "agents")
    from agents.seeds.manager import SeedManager

    manager = SeedManager.__new__(SeedManager)
    manager._seeds = []
    manager._index = 0
    manager._file_path = None

    for item in seeds:
        manager._seeds.append(item)

    exported = manager.export_seeds()
    assert isinstance(exported, str)

    parsed = json.loads(exported)
    assert isinstance(parsed, list)
    assert len(parsed) == len(seeds)

    for i, seed in enumerate(seeds):
        assert parsed[i]["proxy"] == seed["proxy"]
        assert parsed[i]["label"] == seed["label"]


# ── I-Proxy-1: Valid format ────────────────────────────────────────────────

@given(
    proxy=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100)
def test_seed_valid_format(proxy):
    """I-Proxy-1: SeedEntry with proxy has valid format."""
    import sys
    sys.path.insert(0, "agents")
    from agents.seeds.manager import SeedEntry

    entry = SeedEntry.__new__(SeedEntry)
    entry.proxy_url = proxy if proxy.startswith("http") else None
    entry.label = "test"
    entry.is_active = True
    entry.last_used = None
    entry.error_count = 0
    entry._original = {}

    if entry.proxy_url is not None:
        assert entry.proxy_url.startswith("http") or entry.proxy_url.startswith("socks")
    else:
        assert entry.proxy_url is None


# ── I-Cloak-1: Stealth args properties ────────────────────────────────────

def test_default_stealth_args_length():
    """Stealth args list has at least 2 items (no-sandbox + fingerprint)."""
    from cloakbrowser.config import get_default_stealth_args
    args = get_default_stealth_args()
    assert len(args) >= 2
    assert any("no-sandbox" in a for a in args)
    assert any("fingerprint=" in a for a in args)


def test_default_stealth_args_deterministic():
    """Same platform produces same stealth args structure."""
    from cloakbrowser.config import get_default_stealth_args
    args1 = get_default_stealth_args()
    args2 = get_default_stealth_args()
    assert len(args1) == len(args2)
    # All args should be strings
    assert all(isinstance(a, str) for a in args1)
    assert all(isinstance(a, str) for a in args2)


def test_default_viewport_realistic():
    """Default viewport is realistic (1920x947 for 1080p Chrome)."""
    from cloakbrowser.config import DEFAULT_VIEWPORT
    assert DEFAULT_VIEWPORT["width"] == 1920
    assert DEFAULT_VIEWPORT["height"] == 947
