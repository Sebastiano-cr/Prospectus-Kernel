from pydantic import BaseModel
from typing import Any


class CostProfile(BaseModel):
    cost_per_call_usd: float
    tokens_per_call_avg: int
    currency: str = "USD"


class LatencyProfile(BaseModel):
    p50_ms: int
    p95_ms: int
    p99_ms: int


class Capability(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    provider_requirements: list[str]
    cost_profile: CostProfile
    latency_profile: LatencyProfile
    deterministic: bool = False
    tags: list[str] = []


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def list_by_tag(self, tag: str) -> list[Capability]:
        return [c for c in self._capabilities.values() if tag in c.tags]

    def find_by_provider(self, provider: str) -> list[Capability]:
        return [c for c in self._capabilities.values() if provider in c.provider_requirements]

    def all(self) -> list[Capability]:
        return list(self._capabilities.values())
