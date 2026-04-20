"""End-to-end: multi-agent draft → gossip → collect signatures → anchor."""
from mnemosyne import Triple, KnowledgeAsset
from mnemosyne.client import AnchorClient, NullTransport
from harmonia import (
    Ed25519Signer,
    SignedKA,
    ConsensusPolicy,
    InMemoryLineageStore,
    InProcessRelay,
    ConsensusAnchor,
)


def test_multi_agent_consensus_roundtrip():
    # Five agents in a paranet; M-of-N = 3-of-5
    agents = [Ed25519Signer.generate() for _ in range(5)]
    authorized = frozenset(a.pubkey for a in agents)

    policy = ConsensusPolicy(authorized_signers=authorized, threshold=3)
    lineage = InMemoryLineageStore()
    transport = NullTransport()
    anchor_client = AnchorClient(transport=transport)
    consensus_anchor = ConsensusAnchor(
        policy=policy, lineage=lineage, anchor_client=anchor_client
    )
    relay = InProcessRelay()

    # Agent 0 drafts a KA
    proposer = agents[0]
    ka = KnowledgeAsset(
        paranet="urn:muse:calliope",
        triples=(
            Triple("urn:concept:9", "urn:mnem:pool", "reasoning"),
            Triple("urn:concept:9",
                   "http://www.w3.org/2004/02/skos/core#prefLabel",
                   "bronze-pendulum"),
        ),
    )
    draft = SignedKA(ka=ka, proposer=proposer.pubkey, confidence=0.87)
    draft = draft.add_signature(proposer.sign(draft.signed_message()))
    relay.broadcast(draft)

    # Peers independently re-sign after inspecting the draft from the relay
    latest = relay.log[-1]
    for agent in agents[1:4]:  # agents 1, 2, 3 co-sign → total 4 valid sigs
        sig = agent.sign(latest.signed_message())
        latest = latest.add_signature(sig)
        relay.broadcast(latest)

    final = relay.log[-1]
    result = consensus_anchor.submit(final)

    # Consensus reached, anchored, lineage recorded
    assert result is not None
    assert result["status"] == "recorded"
    assert result["quorum"] == (4, 3)
    assert transport.calls[0]["envelope"]["ka_id"] == ka.id()
    assert lineage.get(ka.id()).proposer == proposer.pubkey


def test_sub_quorum_does_not_anchor():
    agents = [Ed25519Signer.generate() for _ in range(5)]
    policy = ConsensusPolicy(
        authorized_signers=frozenset(a.pubkey for a in agents),
        threshold=3,
    )
    lineage = InMemoryLineageStore()
    transport = NullTransport()
    anchor_client = AnchorClient(transport=transport)
    consensus_anchor = ConsensusAnchor(
        policy=policy, lineage=lineage, anchor_client=anchor_client
    )

    ka = KnowledgeAsset(
        paranet="urn:muse:clio",
        triples=(Triple("urn:fact:1", "urn:mnem:pool", "factuality"),),
    )
    draft = SignedKA(ka=ka, proposer=agents[0].pubkey)
    # Only two signers — below threshold
    for a in agents[:2]:
        draft = draft.add_signature(a.sign(draft.signed_message()))

    assert consensus_anchor.submit(draft) is None
    assert transport.calls == []
    assert len(lineage) == 0
