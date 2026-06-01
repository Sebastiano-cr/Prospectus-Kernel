import json
import uuid
from datetime import datetime, timezone
from typing import Callable, Awaitable
from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    correlation_id: str
    causation_id: str | None = None
    tenant_id: str
    session_id: str
    actor_id: str
    payload: dict
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        event_type: str,
        session_id: str,
        actor_id: str,
        tenant_id: str,
        payload: dict,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> "Event":
        return cls(
            event_type=event_type,
            correlation_id=correlation_id or str(uuid.uuid4()),
            causation_id=causation_id,
            tenant_id=tenant_id,
            session_id=session_id,
            actor_id=actor_id,
            payload=payload,
        )


class EventBus:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._published: set[str] = set()
        self._streams: dict[str, list[dict]] = {}

    def _stream_key(self, session_id: str) -> str:
        return f"kirin:stream:{session_id}"

    async def publish(self, event: Event) -> None:
        if event.event_id in self._published:
            return
        stream_key = self._stream_key(event.session_id)
        if stream_key not in self._streams:
            self._streams[stream_key] = []
        self._streams[stream_key].append({"event": event, "data": event.model_dump_json()})
        self._published.add(event.event_id)

    async def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        pass

    async def publish_to_topic(self, event: Event) -> None:
        if event.event_id in self._published:
            return
        topic_stream = f"kirin:topic:{event.event_type}"
        if topic_stream not in self._streams:
            self._streams[topic_stream] = []
        self._streams[topic_stream].append({"event": event, "data": event.model_dump_json()})
        self._published.add(event.event_id)
