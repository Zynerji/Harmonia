from __future__ import annotations
from dataclasses import dataclass
from .signing import Signature, verify_signature
from .signed_ka import SignedKA


@dataclass(frozen=True)
class ConsensusPolicy:
    """An M-of-N threshold policy over a fixed signer set.

    - `authorized_signers` is the set of public keys whose signatures
      are allowed to count toward consensus. Any signature from a key
      outside this set is ignored (not rejected — just uncounted).
    - `threshold` is the minimum number of distinct valid signatures
      required. Duplicate signatures from the same key count once.
    - A signature is valid iff it cryptographically verifies against
      the SignedKA's Merkle root.
    """
    authorized_signers: frozenset[bytes]
    threshold: int

    def __post_init__(self) -> None:
        if self.threshold < 1:
            raise ValueError("threshold M must be >= 1")
        if self.threshold > len(self.authorized_signers):
            raise ValueError(
                f"threshold M={self.threshold} cannot exceed number of "
                f"authorized signers N={len(self.authorized_signers)}"
            )

    def valid_signatures(self, signed_ka: SignedKA) -> list[Signature]:
        message = signed_ka.signed_message()
        seen: set[bytes] = set()
        valid: list[Signature] = []
        for s in signed_ka.signatures:
            if s.pubkey in seen:
                continue
            if s.pubkey not in self.authorized_signers:
                continue
            if verify_signature(s, message):
                valid.append(s)
                seen.add(s.pubkey)
        return valid

    def is_satisfied(self, signed_ka: SignedKA) -> bool:
        return len(self.valid_signatures(signed_ka)) >= self.threshold

    def quorum_progress(self, signed_ka: SignedKA) -> tuple[int, int]:
        """(current_valid_count, threshold) — useful for UI / status."""
        return (len(self.valid_signatures(signed_ka)), self.threshold)
