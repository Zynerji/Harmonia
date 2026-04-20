from mnemosyne import Triple, KnowledgeAsset
from harmonia import Ed25519Signer, SignedKA, InMemoryLineageStore


def _signed_ka(proposer, co_signers, label="phi", parent=None):
    ka = KnowledgeAsset(
        paranet="urn:muse:calliope",
        triples=(Triple(f"urn:c:{label}", "urn:mnem:pool", "reasoning"),),
    )
    signed = SignedKA(
        ka=ka,
        proposer=proposer.pubkey,
        lineage_parent=parent,
        observed_at="2026-04-20T12:00:00Z",
        confidence=0.82,
    )
    for s in co_signers:
        signed = signed.add_signature(s.sign(signed.signed_message()))
    return signed


def test_record_and_retrieve():
    store = InMemoryLineageStore()
    proposer = Ed25519Signer.generate()
    cosigners = [Ed25519Signer.generate() for _ in range(2)]
    signed = _signed_ka(proposer, cosigners)
    rec = store.record(signed)
    assert rec.ka_id == signed.ka_id
    assert rec.proposer == proposer.pubkey
    assert set(rec.co_signers) == {c.pubkey for c in cosigners}
    assert store.get(signed.ka_id) == rec


def test_lineage_parent_child():
    store = InMemoryLineageStore()
    proposer = Ed25519Signer.generate()
    parent_signed = _signed_ka(proposer, [], label="parent")
    store.record(parent_signed)

    child_signed = _signed_ka(proposer, [], label="child", parent=parent_signed.ka_id)
    store.record(child_signed)

    children = store.children(parent_signed.ka_id)
    assert len(children) == 1
    assert children[0].ka_id == child_signed.ka_id


def test_all_records_and_len():
    store = InMemoryLineageStore()
    proposer = Ed25519Signer.generate()
    for i in range(3):
        store.record(_signed_ka(proposer, [], label=f"k{i}"))
    assert len(store) == 3
    assert len(store.all_records()) == 3


def test_missing_ka_id_returns_none():
    store = InMemoryLineageStore()
    assert store.get("does-not-exist") is None
    assert store.children("does-not-exist") == []
