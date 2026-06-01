"""Seed management for CloakBrowser proxy rotation."""
import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class SeedEntry:
    """A single seed entry with proxy configuration."""
    proxy_url: Optional[str] = None
    label: str = ""
    is_active: bool = True
    last_used: Optional[datetime] = None
    error_count: int = 0
    _original: dict = field(default_factory=dict, repr=False)


class SeedManager:
    """Manages CloakBrowser seeds for proxy rotation.

    Seeds are stored in a JSON file and loaded on initialization.
    Rotation uses round-robin with deterministic ordering.
    """

    def __init__(self, file_path: str = "seeds.json"):
        self._file_path = Path(file_path)
        self._seeds: List[dict] = []
        self._index = 0
        self._load()

    def _load(self):
        """Load seeds from file."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r") as f:
                    self._seeds = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._seeds = []
        else:
            self._seeds = []

    def _save(self):
        """Save seeds to file."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "w") as f:
            json.dump(self._seeds, f, indent=2, default=str)

    def get_random_seed(self) -> SeedEntry:
        """Get next seed in round-robin rotation."""
        if not self._seeds:
            return SeedEntry()

        entry = self._seeds[self._index % len(self._seeds)]
        self._index = (self._index + 1) % len(self._seeds)

        return SeedEntry(
            proxy_url=entry.get("proxy"),
            label=entry.get("label", ""),
            is_active=entry.get("is_active", True),
            last_used=entry.get("last_used"),
            error_count=entry.get("error_count", 0),
            _original=entry,
        )

    def export_seeds(self) -> str:
        """Export seeds as JSON string."""
        return json.dumps(self._seeds, indent=2, default=str)

    def import_seeds(self, json_str: str) -> int:
        """Import seeds from JSON string. Returns count imported."""
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                self._seeds = data
                self._save()
                return len(data)
        except (json.JSONDecodeError, TypeError):
            pass
        return 0

    def mark_error(self, label: str):
        """Mark a seed as having an error."""
        for entry in self._seeds:
            if entry.get("label") == label:
                entry["error_count"] = entry.get("error_count", 0) + 1
                entry["is_active"] = entry["error_count"] < 3
                break
        self._save()

    def reset_errors(self, label: str):
        """Reset error count for a seed."""
        for entry in self._seeds:
            if entry.get("label") == label:
                entry["error_count"] = 0
                entry["is_active"] = True
                break
        self._save()

    @property
    def active_seeds(self) -> List[SeedEntry]:
        """Return list of active seeds."""
        return [
            SeedEntry(
                proxy_url=e.get("proxy"),
                label=e.get("label", ""),
                is_active=True,
                last_used=e.get("last_used"),
                error_count=e.get("error_count", 0),
                _original=e,
            )
            for e in self._seeds
            if e.get("is_active", True)
        ]

    @property
    def count(self) -> int:
        return len(self._seeds)

    @property
    def active_count(self) -> int:
        return len([e for e in self._seeds if e.get("is_active", True)])
