"""
[DEPRECATED] Memory factory — was replaced by agents/runtime.py.

This file is kept for reference only and will be removed in a future version.
All memory manager initialization is now handled directly in agents/runtime.py.
"""
import logging
from typing import Dict, Any, Optional
from .base import BaseMemoryManager

logger = logging.getLogger(__name__)

# NOTE: This class is no longer used. Memory managers are initialized
# directly in agents/runtime.py. Kept here to avoid breaking any
# external imports that may reference this module path.
class MemoryFactory:
    """
    [DEPRECATED] Use agents.runtime.initialize_memory_managers() instead.
    """
    pass
