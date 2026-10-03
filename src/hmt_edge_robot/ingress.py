"""NF-SEC-02: bounded ASGI ingress before parsing; one private worker."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Callable


class BoundedIngress:
    def __init__(self, app: Callable, max_bytes: int = 16384, burst: int = 120) -> None:
        self.app, self.max_bytes, self.burst = app, max_bytes, burst
        self.arrivals: deque[float] = deque(maxlen=burst)

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        while self.arrivals and now - self.arrivals[0] >= 60:
            self.arrivals.popleft()
        if len(self.arrivals) >= self.burst:
            await self._reject(send, 429, b'"RATE_LIMITED"')
            return
        self.arrivals.append(now)
        body = bytearray()
        deadline = now + 5
        while True:
            try:
                packet = await asyncio.wait_for(
                    receive(), timeout=max(0.001, deadline - time.monotonic())
                )
            except TimeoutError:
                await self._reject(send, 408, b'"REQUEST_TIMEOUT"')
                return
            if packet["type"] == "http.disconnect":
                return
            body.extend(packet.get("body", b""))
            if len(body) > self.max_bytes:
                await self._reject(send, 413, b'"REQUEST_TOO_LARGE"')
                return
            if not packet.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    async def _reject(self, send: Callable, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
