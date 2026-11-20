from collections import OrderedDict
from collections.abc import Callable, Hashable
from threading import Lock
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class ReadCache:
    """One bounded cache per reader process. Only detached response schemas are stored."""

    def __init__(self, capacity: int = 32):
        self.entries = OrderedDict()
        self.capacity = capacity
        self.lock = Lock()
        self.load_locks = [Lock() for _ in range(8)]

    def get(self, key: Hashable, ttl: int, load: Callable[[], T]) -> T:
        if ttl == 0:
            return load()
        with self.load_locks[hash(key) % len(self.load_locks)]:
            with self.lock:
                entry = self.entries.get(key)
                if entry and entry[0] > monotonic():
                    self.entries.move_to_end(key)
                    return entry[1]
            result = load()
            with self.lock:
                self.entries[key] = (monotonic() + ttl, result)
                self.entries.move_to_end(key)
                if len(self.entries) > self.capacity:
                    self.entries.popitem(last=False)
            return result


class RequestBudget:
    """Fixed one-minute window, used only on the public ASGI event loop."""

    def __init__(self, per_client: int, total: int):
        self.per_client = per_client
        self.total = total
        self.minute = -1
        self.clients: dict[str, int] = {}
        self.used = 0

    def allow(self, client: str) -> bool:
        minute = int(monotonic() // 60)
        if self.minute != minute:
            self.minute = minute
            self.clients.clear()
            self.used = 0
        used = self.clients.get(client, 0)
        if self.used >= self.total or used >= self.per_client:
            return False
        self.used += 1
        self.clients[client] = used + 1
        return True
