"""In-process pub/sub fanout for the rail SSE stream.

Every connected browser gets its own asyncio.Queue; publish() copies the event
to each. Slow/dead clients are dropped rather than blocking the publisher.
"""
import asyncio
from typing import Any

_clients: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _clients.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _clients.discard(q)


def publish(event: dict[str, Any]) -> None:
    for q in list(_clients):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            _clients.discard(q)
