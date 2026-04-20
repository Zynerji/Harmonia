from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Optional
from mnemosyne import KnowledgeAsset
from .signing import Signature


@dataclass(frozen=True)
class SignedKA:
    """A Knowledge Asset wrapped with multi-agent signatures and lineage.

    - `ka` is the underlying Mnemosyne KnowledgeAsset.
    - `proposer` is the raw 32-byte Ed25519 public key of the agent that
      drafted this KA.
    - `signatures` is an ordered tuple of Signature objects. The signed
      message is always the KA's Merkle root (`ka.root()`), never the
      JSON-LD body — so signatures are portable across serializations.
    - `lineage_parent` optionally points to a predecessor KA's id.
    - `observed_at` is a caller-supplied timestamp string (ISO-8601
      recommended). Harmonia does not interpret it.
    - `confidence` is an optional aggregated confidence score in [0, 1].
    """
    ka: KnowledgeAsset
    proposer: bytes
    signatures: tuple[Signature, ...] = field(default_factory=tuple)
    lineage_parent: Optional[str] = None
    observed_at: Optional[str] = None
    confidence: Optional[float] = None

    def signed_message(self) -> bytes:
        return self.ka.root()

    def add_signature(self, signature: Signature) -> "SignedKA":
        return replace(self, signatures=self.signatures + (signature,))

    def with_signatures(self, signatures: tuple[Signature, ...]) -> "SignedKA":
        return replace(self, signatures=tuple(signatures))

    @property
    def ka_id(self) -> str:
        return self.ka.id()

    @property
    def signer_pubkeys(self) -> frozenset[bytes]:
        return frozenset(s.pubkey for s in self.signatures)
