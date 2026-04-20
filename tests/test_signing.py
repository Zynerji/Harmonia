import pytest
from harmonia import Ed25519Signer, Signature, verify_signature


def test_sign_and_verify():
    s = Ed25519Signer.generate()
    msg = b"the quick brown fox"
    sig = s.sign(msg)
    assert isinstance(sig, Signature)
    assert sig.pubkey == s.pubkey
    assert len(sig.pubkey) == 32
    assert len(sig.sig) == 64
    assert verify_signature(sig, msg)


def test_verify_rejects_tampered_message():
    s = Ed25519Signer.generate()
    sig = s.sign(b"original")
    assert not verify_signature(sig, b"tampered")


def test_verify_rejects_tampered_signature():
    s = Ed25519Signer.generate()
    sig = s.sign(b"msg")
    bad = Signature(pubkey=sig.pubkey, sig=b"\x00" * 64)
    assert not verify_signature(bad, b"msg")


def test_verify_rejects_wrong_pubkey():
    s1 = Ed25519Signer.generate()
    s2 = Ed25519Signer.generate()
    sig = s1.sign(b"msg")
    forged = Signature(pubkey=s2.pubkey, sig=sig.sig)
    assert not verify_signature(forged, b"msg")


def test_signature_size_validation():
    with pytest.raises(ValueError):
        Signature(pubkey=b"\x00" * 31, sig=b"\x00" * 64)
    with pytest.raises(ValueError):
        Signature(pubkey=b"\x00" * 32, sig=b"\x00" * 63)


def test_from_private_bytes_round_trip():
    s1 = Ed25519Signer.generate()
    raw = s1._sk.private_bytes_raw()
    s2 = Ed25519Signer.from_private_bytes(raw)
    assert s1.pubkey == s2.pubkey
    sig = s2.sign(b"msg")
    assert verify_signature(sig, b"msg")


def test_from_private_bytes_length_check():
    with pytest.raises(ValueError):
        Ed25519Signer.from_private_bytes(b"short")
