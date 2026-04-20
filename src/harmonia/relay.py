from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable
from .signed_ka import SignedKA


@runtime_checkable
class RelayTransport(Protocol):
    """Broadcast / subscribe surface for peer gossip of SignedKA drafts.

    Implementations may be in-process (for tests), libp2p-backed, or
    anything in between. Harmonia's core logic does not assume network.
    """

    def broadcast(self, signed_ka: SignedKA) -> None: ...
    def subscribe(self, callback: Callable[[SignedKA], None]) -> None: ...


@dataclass
class InProcessRelay:
    """Zero-network relay that fans every broadcast out to all subscribers
    synchronously, and keeps a log of every message for inspection.

    Use in unit tests and single-process multi-agent simulations.
    """
    _subscribers: list[Callable[[SignedKA], None]] = field(default_factory=list)
    _log: list[SignedKA] = field(default_factory=list)

    def broadcast(self, signed_ka: SignedKA) -> None:
        self._log.append(signed_ka)
        for cb in list(self._subscribers):
            cb(signed_ka)

    def subscribe(self, callback: Callable[[SignedKA], None]) -> None:
        self._subscribers.append(callback)

    @property
    def log(self) -> list[SignedKA]:
        return list(self._log)

    def __len__(self) -> int:
        return len(self._log)
