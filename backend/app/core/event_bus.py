"""
In-memory event bus — pushes realtime events to Socket.IO subscribers
(operators, buyers, insurance oracles, carrier SLA dashboards).

Author: Praveen Sudireddy
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Callable, Awaitable

import socketio


class EventBus:
    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self.subscribers: Dict[str, List[Callable[[dict], Awaitable[None]]]] = {}

    async def emit(self, event: str, payload: Dict[str, Any], room: str | None = None):
        await self.sio.emit(event, payload, to=room)
        for cb in self.subscribers.get(event, []):
            try:
                await cb(payload)
            except Exception as e:
                print(f"[eventbus] subscriber error on {event}: {e}")

    def on(self, event: str, cb: Callable[[dict], Awaitable[None]]):
        self.subscribers.setdefault(event, []).append(cb)


bus: EventBus | None = None
def init_bus(sio: socketio.AsyncServer) -> EventBus:
    global bus
    bus = EventBus(sio)
    return bus
def get_bus() -> EventBus:
    assert bus is not None, "event bus not initialised"
    return bus
