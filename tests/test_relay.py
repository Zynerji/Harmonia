from mnemosyne import Triple, KnowledgeAsset
from harmonia import Ed25519Signer, SignedKA, InProcessRelay


def _signed(proposer) -> SignedKA:
    ka = KnowledgeAsset(
        paranet="urn:muse:calliope",
        triples=(Triple("urn:c:1", "urn:mnem:pool", "reasoning"),),
    )
    return SignedKA(ka=ka, proposer=proposer.pubkey)


def test_broadcast_reaches_all_subscribers():
    relay = InProcessRelay()
    received_a: list[SignedKA] = []
    received_b: list[SignedKA] = []
    relay.subscribe(received_a.append)
    relay.subscribe(received_b.append)

    proposer = Ed25519Signer.generate()
    signed = _signed(proposer)
    relay.broadcast(signed)

    assert received_a == [signed]
    assert received_b == [signed]


def test_log_records_every_broadcast():
    relay = InProcessRelay()
    proposer = Ed25519Signer.generate()
    signed = _signed(proposer)
    for _ in range(3):
        relay.broadcast(signed)
    assert len(relay) == 3
    assert relay.log == [signed, signed, signed]


def test_subscriber_added_after_broadcast_does_not_see_past():
    relay = InProcessRelay()
    proposer = Ed25519Signer.generate()
    signed = _signed(proposer)
    relay.broadcast(signed)

    received: list[SignedKA] = []
    relay.subscribe(received.append)
    assert received == []

    relay.broadcast(signed)
    assert received == [signed]
