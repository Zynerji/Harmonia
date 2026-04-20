from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional
from .consensus import ConsensusPolicy
from .lineage import LineageStore
from .signed_ka import SignedKA


@dataclass
class ConsensusAnchor:
    """Consensus-gated anchor: a SignedKA is only forwarded to the
    underlying Mnemosyne AnchorClient once the policy is satisfied.

    The `anchor_client` parameter is typed Any to avoid a hard import
    of mnemosyne.client.AnchorClient at module scope — callers inject
    any object with an `.anchor(ka) -> dict` method, which keeps this
    module trivially testable.
    """
    policy: ConsensusPolicy
    lineage: LineageStore
    anchor_client: Any

    def submit(self, signed_ka: SignedKA) -> Optional[dict[str, Any]]:
        """Submit a SignedKA. If the consensus policy is satisfied,
        record lineage and anchor the underlying KA via the injected
        client. Return the anchor result, or None if quorum is not met.
        """
        if not self.policy.is_satisfied(signed_ka):
            return None
        self.lineage.record(signed_ka)
        result = self.anchor_client.anchor(signed_ka.ka)
        return {
            "quorum": self.policy.quorum_progress(signed_ka),
            "lineage_recorded": True,
            **result,
        }

    def progress(self, signed_ka: SignedKA) -> tuple[int, int]:
        return self.policy.quorum_progress(signed_ka)
