"""
Kirin Runtime — Cline-compatible tool definitions for the Language Games Engine.

Provides Python-based tool interfaces that expose the same semantics as
Cline SDK tools: discourse_extract, resonance_lookup, prospect_generator, memory_store.
"""
from .tools import (
    discourse_extract,
    resonance_lookup,
    prospect_generator,
    memory_store,
)
from .pipeline import full_discourse_analysis

__all__ = [
    "discourse_extract",
    "resonance_lookup",
    "prospect_generator",
    "memory_store",
    "full_discourse_analysis",
]
