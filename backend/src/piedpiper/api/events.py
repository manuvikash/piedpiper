"""In-memory event bus for real-time SSE streaming."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator


class EventBus:
    """Pub/sub event bus keyed by session_id with replay buffer."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._buffer: dict[str, list[dict[str, Any]]] = {}

    async def emit(
        self,
        session_id: str,
        worker_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Push an event to all subscribers and buffer it."""
        event = {
            "type": event_type,
            "worker_id": worker_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.setdefault(session_id, []).append(event)
        for queue in self._subscribers.get(session_id, []):
            await queue.put(event)

    async def subscribe(self, session_id: str) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted events. Replays buffer then streams live."""
        queue: asyncio.Queue = asyncio.Queue()

        # Register FIRST so we don't miss events between replay and listen
        self._subscribers.setdefault(session_id, []).append(queue)

        try:
            # Snapshot the buffer length at registration time
            buffered = list(self._buffer.get(session_id, []))
            buffered_count = len(buffered)

            # Replay buffered events
            for event in buffered:
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "session_done":
                    return

            # Drain any events that arrived in the queue during replay
            # (these are duplicates of buffered events + any new ones)
            # Skip the first N that overlap with our buffer snapshot
            skipped = 0
            while True:
                try:
                    event = queue.get_nowait()
                    skipped += 1
                    if skipped > buffered_count:
                        # This is a genuinely new event
                        yield f"data: {json.dumps(event)}\n\n"
                        if event.get("type") == "session_done":
                            return
                except asyncio.QueueEmpty:
                    break

            # Now stream live
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "session_done":
                    break
        finally:
            subs = self._subscribers.get(session_id, [])
            if queue in subs:
                subs.remove(queue)
            if session_id in self._subscribers and not self._subscribers[session_id]:
                del self._subscribers[session_id]

    def cleanup_session(self, session_id: str) -> None:
        """Remove buffered events for a session to free memory."""
        self._buffer.pop(session_id, None)

    def make_emitter(self, session_id: str):
        """Create a bound emitter function for a specific session."""

        async def emitter(worker_id: str, event_type: str, data: dict[str, Any]) -> None:
            await self.emit(session_id, worker_id, event_type, data)

        return emitter


# Global singleton
event_bus = EventBus()
