import pytest
from mnemosyne import Triple, KnowledgeAsset
from harmonia import Ed25519Signer, ConsensusPolicy, SignedKA


def _ka() -> KnowledgeAsset:
    return KnowledgeAsset(
        paranet="urn:muse:calliope",
        triples=(Triple("urn:c:1", "urn:mnem:pool", "reasoning"),),
    )


def _signers(n: int) -> list[Ed25519Signer]:
    return [Ed25519Signer.generate() for _ in range(n)]


def test_threshold_below_fails():
    signers = _signers(5)
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    ka = _ka()
    signed = SignedKA(ka=ka, proposer=signers[0].pubkey)
    # 2 signatures, need 3
    for s in signers[:2]:
        signed = signed.add_signature(s.sign(signed.signed_message()))
    assert not policy.is_satisfied(signed)
    assert policy.quorum_progress(signed) == (2, 3)


def test_threshold_met_passes():
    signers = _signers(5)
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    ka = _ka()
    signed = SignedKA(ka=ka, proposer=signers[0].pubkey)
    for s in signers[:3]:
        signed = signed.add_signature(s.sign(signed.signed_message()))
    assert policy.is_satisfied(signed)
    assert policy.quorum_progress(signed) == (3, 3)


def test_duplicate_signatures_counted_once():
    signers = _signers(5)
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=3,
    )
    ka = _ka()
    signed = SignedKA(ka=ka, proposer=signers[0].pubkey)
    # Same signer signs three times — must still count as 1
    for _ in range(3):
        signed = signed.add_signature(signers[0].sign(signed.signed_message()))
    assert not policy.is_satisfied(signed)
    assert policy.quorum_progress(signed) == (1, 3)


def test_unauthorized_signer_ignored():
    authorized = _signers(3)
    outsider = Ed25519Signer.generate()
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in authorized),
        threshold=2,
    )
    ka = _ka()
    signed = SignedKA(ka=ka, proposer=authorized[0].pubkey)
    signed = signed.add_signature(authorized[0].sign(signed.signed_message()))
    signed = signed.add_signature(outsider.sign(signed.signed_message()))
    # Only 1 authorized sig, needs 2
    assert not policy.is_satisfied(signed)
    assert policy.quorum_progress(signed) == (1, 2)


def test_signature_over_wrong_message_rejected():
    signers = _signers(3)
    policy = ConsensusPolicy(
        authorized_signers=frozenset(s.pubkey for s in signers),
        threshold=2,
    )
    ka = _ka()
    signed = SignedKA(ka=ka, proposer=signers[0].pubkey)
    # Craft a sig over the wrong message but attach it anyway
    good_sig = signers[0].sign(signed.signed_message())
    bad_sig = signers[1].sign(b"not-the-root")
    signed = signed.add_signature(good_sig).add_signature(bad_sig)
    assert not policy.is_satisfied(signed)
    assert policy.quorum_progress(signed) == (1, 2)


def test_policy_rejects_impossible_thresholds():
    signers = _signers(3)
    with pytest.raises(ValueError):
        ConsensusPolicy(
            authorized_signers=frozenset(s.pubkey for s in signers),
            threshold=0,
        )
    with pytest.raises(ValueError):
        ConsensusPolicy(
            authorized_signers=frozenset(s.pubkey for s in signers),
            threshold=4,
        )
