from dataclasses import dataclass, field
from typing import Any
from mnemosyne import Triple, KnowledgeAsset
from harmonia import (
    Ed25519Signer,
    SignedKA,
    ConsensusPolicy,
    InMemoryLineageStore,
    ConsensusAnchor,
)


@dataclass
class RecordingClient:
    """Stand-in for mnemosyne.client.AnchorClient for test purposes."""
    calls: list[KnowledgeAsset] = field(default_factory=list)

    def anchor(self, ka: KnowledgeAsset) -> dict[str, Any]:
        self.calls.append(ka)
        return {"status": "recorded", "ka_id": ka.id()}


def _make_signed(proposer, cosigners, n_sigs: int) -> SignedKA:
    ka = KnowledgeAsset(
        paranet="urn:muse:calliope",
        triples=(Triple("urn:c:1", "urn:mnem:pool", "reasoning"),),
    )
    signed = SignedKA(ka=ka, proposer=proposer.pubkey)
    for s in cosigners[:n_sigs]:
        signed = signed.add_signature(s.sign(signed.signed_message()))
    return signed


def test_submit_blocks_when_quorum_unmet():
    signers = [Ed25519Signer.generate() for _ in range(5)]
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    lineage = InMemoryLineageStore()
    client = RecordingClient()
    anchor = ConsensusAnchor(policy=policy, lineage=lineage, anchor_client=client)

    signed = _make_signed(signers[0], signers, n_sigs=2)
    result = anchor.submit(signed)
    assert result is None
    assert client.calls == []
    assert len(lineage) == 0


def test_submit_anchors_when_quorum_met():
    signers = [Ed25519Signer.generate() for _ in range(5)]
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    lineage = InMemoryLineageStore()
    client = RecordingClient()
    anchor = ConsensusAnchor(policy=policy, lineage=lineage, anchor_client=client)

    signed = _make_signed(signers[0], signers, n_sigs=4)
    result = anchor.submit(signed)
    assert result is not None
    assert result["status"] == "recorded"
    assert result["quorum"] == (4, 3)
    assert result["lineage_recorded"] is True
    assert len(client.calls) == 1
    assert client.calls[0].id() == signed.ka_id
    assert lineage.get(signed.ka_id) is not None


def test_progress_reports_quorum():
    signers = [Ed25519Signer.generate() for _ in range(5)]
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    anchor = ConsensusAnchor(
        policy=policy,
        lineage=InMemoryLineageStore(),
        anchor_client=RecordingClient(),
    )
    signed = _make_signed(signers[0], signers, n_sigs=2)
    assert anchor.progress(signed) == (2, 3)
