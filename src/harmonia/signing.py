from __future__ import annotations
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature


@dataclass(frozen=True)
class Signature:
    """An Ed25519 signature with its public key attached.

    `pubkey` is the raw 32-byte public key. `sig` is the raw 64-byte
    Ed25519 signature over the message. Messages are never carried
    inside the Signature — the verifier supplies the expected message.
    """
    pubkey: bytes
    sig: bytes

    def __post_init__(self) -> None:
        if len(self.pubkey) != 32:
            raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(self.pubkey)}")
        if len(self.sig) != 64:
            raise ValueError(f"Ed25519 signature must be 64 bytes, got {len(self.sig)}")


class Ed25519Signer:
    """Ed25519 signing keypair. Private key never leaves this object."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._sk = private_key
        self._pk_bytes = private_key.public_key().public_bytes_raw()

    @classmethod
    def generate(cls) -> "Ed25519Signer":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> "Ed25519Signer":
        if len(raw) != 32:
            raise ValueError(f"Ed25519 private key must be 32 bytes, got {len(raw)}")
        return cls(Ed25519PrivateKey.from_private_bytes(raw))

    @property
    def pubkey(self) -> bytes:
        return self._pk_bytes

    def sign(self, message: bytes) -> Signature:
        return Signature(pubkey=self._pk_bytes, sig=self._sk.sign(message))


def verify_signature(signature: Signature, message: bytes) -> bool:
    try:
        pk = Ed25519PublicKey.from_public_bytes(signature.pubkey)
        pk.verify(signature.sig, message)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False
