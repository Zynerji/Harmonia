from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable
from .signed_ka import SignedKA


@dataclass(frozen=True)
class LineageRecord:
    """Provenance record for an anchored or consensus-eligible KA."""
    ka_id: str
    proposer: bytes
    co_signers: tuple[bytes, ...]
    observed_at: Optional[str]
    lineage_parent: Optional[str]
    confidence: Optional[float]


@runtime_checkable
class LineageStore(Protocol):
    def record(self, signed_ka: SignedKA) -> LineageRecord: ...
    def get(self, ka_id: str) -> Optional[LineageRecord]: ...
    def children(self, parent_ka_id: str) -> list[LineageRecord]: ...
    def all_records(self) -> list[LineageRecord]: ...


@dataclass
class InMemoryLineageStore:
    """Volatile, in-memory lineage store. Suitable for tests and single-
    process development. Swap for a persistent backend in production.
    """
    _records: dict[str, LineageRecord] = field(default_factory=dict)

    def record(self, signed_ka: SignedKA) -> LineageRecord:
        rec = LineageRecord(
            ka_id=signed_ka.ka_id,
            proposer=signed_ka.proposer,
            co_signers=tuple(s.pubkey for s in signed_ka.signatures),
            observed_at=signed_ka.observed_at,
            lineage_parent=signed_ka.lineage_parent,
            confidence=signed_ka.confidence,
        )
        self._records[rec.ka_id] = rec
        return rec

    def get(self, ka_id: str) -> Optional[LineageRecord]:
        return self._records.get(ka_id)

    def children(self, parent_ka_id: str) -> list[LineageRecord]:
        return [
            r for r in self._records.values()
            if r.lineage_parent == parent_ka_id
        ]

    def all_records(self) -> list[LineageRecord]:
        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)
