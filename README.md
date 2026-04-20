# Harmonia

**Multi-agent consensus and lineage for Knowledge Assets on the OriginTrail DKG.** Ed25519 M-of-N co-signing, pluggable peer gossip, verifiable provenance — a thin, auditable layer on top of [Mnemosyne](https://github.com/Zynerji/Mnemosyne).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Status: v0.1.0](https://img.shields.io/badge/Status-v0.1.0-green.svg)](#roadmap)
[![Built on: Mnemosyne](https://img.shields.io/badge/Built%20on-Mnemosyne-blue.svg)](https://github.com/Zynerji/Mnemosyne)

Named after **Ἁρμονία** (Harmonia), the Greek goddess of harmony and concord — fitting for a library whose job is to make many agents agree before anything is written to shared memory.

---

## Table of contents

- [Why Harmonia](#why-harmonia)
- [Install](#install)
- [60-second example](#60-second-example)
- [Concepts](#concepts)
- [Architecture](#architecture)
- [Core API](#core-api)
- [End-to-end: multi-agent round trip](#end-to-end-multi-agent-round-trip)
- [Security model](#security-model)
- [Project layout](#project-layout)
- [Development](#development)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Why Harmonia

Mnemosyne gives you a deterministic Knowledge Asset: the same triples always hash to the same Merkle root, so any agent can independently compute and verify the same KA id. That property is necessary but not sufficient. For shared memory to be *trustable*, you also need an answer to:

- Who proposed this KA?
- Who else has independently seen it and agreed to its content?
- How many independent agents does it take before we commit it to a chain?
- How do we keep all of that cryptographically verifiable, not just logged?

Harmonia answers those questions with the smallest possible stack of primitives:

- **Ed25519 signatures** over the KA's Merkle root — so signatures are portable across any serialization of the KA
- **An M-of-N consensus policy** over a fixed, declared signer set — duplicates and unauthorized signers are uncounted, never trusted
- **A lineage store** that records the proposer, the co-signers, the parent KA, and the observation timestamp
- **A relay transport protocol** that is trivially pluggable — in-process for tests, libp2p for production
- **A consensus-gated anchor** that wraps Mnemosyne's `AnchorClient` and only publishes a KA once quorum is met

The design is deliberately narrow. Harmonia does one thing — get multiple agents to cryptographically agree on a KA before it is anchored — and leaves everything else to Mnemosyne or to the caller.

---

## Install

```bash
pip install harmonia-dkg
```

Requires Python 3.11+. Pulls [`mnemosyne-dkg`](https://pypi.org/project/mnemosyne-dkg/) as a dependency, plus [`cryptography`](https://cryptography.io/) for Ed25519.

The Python import name is unchanged — `import harmonia` as always. The PyPI distribution is `harmonia-dkg` for consistency with `mnemosyne-dkg`.

For development with tests:

```bash
git clone https://github.com/Zynerji/Harmonia
cd Harmonia
pip install -e ".[dev]"
pytest
```

---

## 60-second example

```python
from mnemosyne import Triple, KnowledgeAsset
from mnemosyne.client import AnchorClient, NullTransport
from harmonia import (
    Ed25519Signer, SignedKA, ConsensusPolicy,
    InMemoryLineageStore, ConsensusAnchor,
)

# 1. Five agents form a paranet. Consensus policy is 3-of-5.
agents = [Ed25519Signer.generate() for _ in range(5)]
policy = ConsensusPolicy(
    authorized_signers=frozenset(a.pubkey for a in agents),
    threshold=3,
)

# 2. Agent 0 drafts a KA and signs it
ka = KnowledgeAsset(
    paranet="urn:muse:calliope",
    triples=(
        Triple("urn:concept:1", "urn:mnem:pool", "reasoning"),
    ),
)
draft = SignedKA(ka=ka, proposer=agents[0].pubkey, confidence=0.87)
draft = draft.add_signature(agents[0].sign(draft.signed_message()))

# 3. Two more agents co-sign after inspecting the draft
for a in agents[1:3]:
    draft = draft.add_signature(a.sign(draft.signed_message()))

# 4. Hand off to the consensus-gated anchor
consensus_anchor = ConsensusAnchor(
    policy=policy,
    lineage=InMemoryLineageStore(),
    anchor_client=AnchorClient(transport=NullTransport()),
)
result = consensus_anchor.submit(draft)

# 5. Quorum met (3 valid sigs >= threshold 3) → anchored, lineage recorded
assert result["quorum"] == (3, 3)
assert result["lineage_recorded"] is True
```

---

## Concepts

### `Ed25519Signer` / `Signature`

Harmonia uses Ed25519 because it is fast, small, and standardized. Every agent owns a keypair. A `Signature` carries its own public key so verifiers can check origin without a side channel. Signers never expose the private key outside the `Ed25519Signer` object.

### `SignedKA`

A Mnemosyne `KnowledgeAsset` wrapped with:

- the proposer's pubkey,
- a tuple of `Signature`s,
- optional lineage fields (`lineage_parent`, `observed_at`, `confidence`).

All signatures are always over `ka.root()` — the 32-byte Merkle root. This means signatures are portable across any serialization (N-Triples, N-Quads, JSON-LD), and you can never trick a verifier into accepting a sig for the wrong triple set.

### `ConsensusPolicy`

An M-of-N threshold over a fixed signer set. The policy enforces three hard invariants:

1. A signature from a key outside `authorized_signers` is uncounted.
2. Duplicate signatures from the same key count once.
3. A signature that does not cryptographically verify against the KA's Merkle root is uncounted.

The policy also rejects impossible constructions at construction time: `threshold < 1` or `threshold > len(authorized_signers)` raises `ValueError`.

### `LineageStore`

A pluggable provenance log. `InMemoryLineageStore` ships as a volatile default for tests and single-process dev. Harmonia stores the `ka_id`, the proposer pubkey, the co-signer pubkeys, the optional parent-of lineage pointer, the observation timestamp, and the confidence score.

### `RelayTransport`

A `Protocol` describing a broadcast/subscribe surface for peer gossip of `SignedKA` drafts. `InProcessRelay` is the reference implementation — fully synchronous, zero network, logs every message, suitable for tests and multi-agent simulations in a single process. Production deployments supply their own libp2p, NATS, Redis, or custom implementation.

### `ConsensusAnchor`

The glue. Takes a policy, a lineage store, and anything that quacks like Mnemosyne's `AnchorClient` (anything with a `.anchor(ka) -> dict` method). Its `submit()` method:

1. Checks the consensus policy against the `SignedKA`
2. If quorum is met: records lineage, anchors via the underlying client, returns an enriched result dict
3. Otherwise: returns `None` without side effects

---

## Architecture

```
   agent A           agent B           agent C           agent D           agent E
      |                 |                 |                 |                 |
      |  draft + sig    |                 |                 |                 |
      +---------------->|                 |                 |                 |
      |                 |     sig         |                 |                 |
      |<----------------+                 |                 |                 |
      |                 |                 |      sig        |                 |
      |<----------------------------------+                 |                 |
      |                                                                        |
      v
   +-----------------------------------------------------------------+
   |  SignedKA (ka, proposer, signatures[])                          |
   +-----------------------------------------------------------------+
                               |
                               v
   +-----------------------------------------------------------------+
   |  ConsensusPolicy.is_satisfied(signed_ka)                        |
   |    - sigs from authorized set                                   |
   |    - deduplicated by pubkey                                     |
   |    - cryptographically valid over ka.root()                     |
   |    - count >= threshold M                                       |
   +-------------------+---------------------------------------------+
                       | (yes)
                       v
   +-------------------+------------------+----------------------------+
   |                                      |                            |
   v                                      v                            v
 LineageStore.record(signed_ka)  AnchorClient.anchor(signed_ka.ka)   return
 (proposer, co-signers,          (Mnemosyne JSON-LD envelope,        {status,
  parent, confidence,             NullTransport or DkgNodeTransport)  quorum, ...}
  observed_at)
```

The peer relay is deliberately factored out of the consensus path. Harmonia does not care how a `SignedKA` got to a given agent — only whether the policy is satisfied when `submit()` is called. That keeps the consensus logic small, testable without network, and independent of transport choices.

---

## Core API

### `Ed25519Signer`

```python
from harmonia import Ed25519Signer

s = Ed25519Signer.generate()
s.pubkey                           # bytes of length 32
sig = s.sign(b"the quick brown fox")
# sig.pubkey, sig.sig

s2 = Ed25519Signer.from_private_bytes(raw_32_bytes)
```

### `Signature`

```python
from harmonia import Signature, verify_signature

sig = Signature(pubkey=pubkey_bytes, sig=sig_bytes)   # validated lengths
verify_signature(sig, message_bytes) -> bool
```

### `SignedKA`

```python
from harmonia import SignedKA

signed = SignedKA(
    ka=knowledge_asset,
    proposer=signer.pubkey,
    lineage_parent="<ka_id of predecessor>",   # optional
    observed_at="2026-04-20T12:00:00Z",        # optional
    confidence=0.82,                            # optional, in [0,1]
)

# Immutable updates
signed = signed.add_signature(sig)
signed = signed.with_signatures(tuple_of_sigs)

# Introspection
signed.signed_message()   # bytes of ka.root()
signed.ka_id              # hex string
signed.signer_pubkeys     # frozenset of pubkeys in this draft
```

### `ConsensusPolicy`

```python
from harmonia import ConsensusPolicy

policy = ConsensusPolicy(
    authorized_signers=frozenset({pk1, pk2, pk3, pk4, pk5}),
    threshold=3,
)

policy.is_satisfied(signed_ka)     # bool
policy.valid_signatures(signed_ka) # list of valid, deduped, authorized sigs
policy.quorum_progress(signed_ka)  # (current_valid_count, threshold)
```

### `LineageStore` / `InMemoryLineageStore`

```python
from harmonia import InMemoryLineageStore

lineage = InMemoryLineageStore()
rec = lineage.record(signed_ka)        # -> LineageRecord
lineage.get(ka_id)                     # -> LineageRecord | None
lineage.children(parent_ka_id)         # -> list[LineageRecord]
lineage.all_records()                  # -> list[LineageRecord]
```

The `LineageStore` is a `Protocol` — any object that implements `record`, `get`, `children`, and `all_records` works. Persistent backends (SQLite, Postgres, custom key-value stores) are straightforward to add.

### `RelayTransport` / `InProcessRelay`

```python
from harmonia import InProcessRelay

relay = InProcessRelay()
relay.subscribe(lambda signed_ka: ...)
relay.broadcast(signed_ka)
relay.log                                # list of all broadcasts
```

### `ConsensusAnchor`

```python
from harmonia import ConsensusAnchor

consensus_anchor = ConsensusAnchor(
    policy=policy,
    lineage=lineage,
    anchor_client=mnemosyne_anchor_client,
)

result = consensus_anchor.submit(signed_ka)
# -> None (below quorum) OR
# -> {"status": ..., "quorum": (n, m), "lineage_recorded": True, ...}

consensus_anchor.progress(signed_ka)     # (current, threshold)
```

---

## End-to-end: multi-agent round trip

```python
from mnemosyne import Triple, KnowledgeAsset
from mnemosyne.client import AnchorClient, NullTransport
from harmonia import (
    Ed25519Signer, SignedKA, ConsensusPolicy,
    InMemoryLineageStore, InProcessRelay, ConsensusAnchor,
)

# 5 agents, 3-of-5 consensus
agents = [Ed25519Signer.generate() for _ in range(5)]
policy = ConsensusPolicy(
    authorized_signers=frozenset(a.pubkey for a in agents),
    threshold=3,
)
lineage = InMemoryLineageStore()
transport = NullTransport()
consensus_anchor = ConsensusAnchor(
    policy=policy,
    lineage=lineage,
    anchor_client=AnchorClient(transport=transport),
)
relay = InProcessRelay()

# Proposer drafts
ka = KnowledgeAsset(
    paranet="urn:muse:calliope",
    triples=(
        Triple("urn:concept:9", "urn:mnem:pool", "reasoning"),
        Triple("urn:concept:9",
               "http://www.w3.org/2004/02/skos/core#prefLabel",
               "bronze-pendulum"),
    ),
)
proposer = agents[0]
draft = SignedKA(ka=ka, proposer=proposer.pubkey, confidence=0.87)
draft = draft.add_signature(proposer.sign(draft.signed_message()))
relay.broadcast(draft)

# Peers re-sign and gossip
latest = relay.log[-1]
for agent in agents[1:4]:
    latest = latest.add_signature(agent.sign(latest.signed_message()))
    relay.broadcast(latest)

# Final draft has 4 valid sigs from authorized signers → quorum met
result = consensus_anchor.submit(relay.log[-1])
assert result["quorum"] == (4, 3)
assert result["status"] == "recorded"
assert transport.calls[0]["envelope"]["ka_id"] == ka.id()
```

The test suite exercises this exact flow end-to-end; see `tests/test_integration.py`.

---

## Security model

Harmonia's cryptographic guarantees hold under a specific, stated threat model.

**Trust assumptions**

- The `authorized_signers` set is curated and correct. Harmonia does not opinion on how signer sets are provisioned — that is a policy question, answered by the deployment (DAO vote, allow-list, PKI, chain registry, etc.).
- The Ed25519 implementation in the `cryptography` package is sound. Harmonia does not roll its own crypto.

**Guarantees**

- **Unforgeability.** A valid signature over `ka.root()` cannot be produced without the corresponding private key. An attacker who does not own a private key in `authorized_signers` cannot increase the valid-signature count.
- **Non-malleability.** The signed message is always `ka.root()` — a SHA-256 domain-separated Merkle root over the canonical triple bytes. The attacker cannot present a signature for a different triple set and claim it covers this KA.
- **Sybil-resistance within the policy.** Duplicate signatures from the same key count once. A single compromised key cannot masquerade as many.
- **No privilege escalation.** `ConsensusPolicy` validates its threshold against the signer-set size at construction time. You cannot demand more signatures than the signer set can produce.

**Non-guarantees**

- Harmonia does not protect against private key compromise — once an attacker holds M of the N private keys, they are the consensus, by design.
- Harmonia does not prevent a malicious proposer from drafting garbage triples — that is a content-quality question. Pair Harmonia with a content-validation step between gossip and signing, or use the `confidence` field plus off-chain scoring.
- `InMemoryLineageStore` and `InProcessRelay` are reference implementations, not production infrastructure. Use persistent stores and network relays in production.

**Recommended handling**

- Generate keypairs inside `Ed25519Signer.generate()`, persist only the private bytes, and load via `Ed25519Signer.from_private_bytes()` when the process restarts.
- Rotate signer sets via `ConsensusPolicy` reconstruction — the type is frozen by design, so you build a new policy per epoch.

---

## Project layout

```
Harmonia/
├── src/harmonia/
│   ├── __init__.py          # public re-exports
│   ├── signing.py           # Ed25519Signer, Signature, verify_signature
│   ├── signed_ka.py         # SignedKA dataclass
│   ├── consensus.py         # ConsensusPolicy (M-of-N threshold)
│   ├── lineage.py           # LineageRecord, LineageStore, InMemoryLineageStore
│   ├── relay.py             # RelayTransport, InProcessRelay
│   └── anchor.py            # ConsensusAnchor
├── tests/
│   ├── test_signing.py
│   ├── test_consensus.py
│   ├── test_lineage.py
│   ├── test_relay.py
│   ├── test_anchor.py
│   └── test_integration.py   # end-to-end, multi-agent
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## Development

```bash
git clone https://github.com/Zynerji/Harmonia
cd Harmonia
pip install -e ".[dev]"
pytest
```

The test suite is hermetic. Every signature, consensus check, lineage record, and end-to-end flow runs in a single process with no network, no live DKG node, and no external services.

---

## Roadmap

| Version | Scope                                                                                              | Status  |
|---------|----------------------------------------------------------------------------------------------------|---------|
| v0.1.0  | Ed25519 signing, M-of-N consensus, in-memory lineage, in-process relay, consensus-gated anchor     | shipped |
| v0.1.1  | PyPI release as `harmonia-dkg`; dependency on `mnemosyne-dkg>=0.1.0` (no more git+ direct refs)     | shipped |
| v0.2    | Persistent lineage backends (SQLite, Postgres); signer-set registries                              | planned |
| v0.3    | FROST threshold signatures — aggregated Schnorr instead of a list of individual Ed25519 sigs        | planned |
| v0.4    | Network relays: libp2p gossip adapter, optional NATS/Redis adapters                                 | planned |
| v0.5    | Byzantine-tolerant policy variants (weighted stakes, reputation-weighted thresholds)                | planned |
| v1.0    | Stable API, PyPI release, documentation site                                                        | planned |

---

## Contributing

Issues, discussion, and pull requests are welcome. For larger changes, please open an issue first so we can discuss the direction before you invest time in a PR.

A few norms:

- New features land with tests. The existing suite is hermetic — keep it that way.
- Cryptographic changes require a strong rationale and, where possible, a reference to an accepted construction. We are not in the business of inventing new primitives.
- Public API changes are SemVer-governed and should be discussed in an issue first.
- Keep the dependency surface small. The only hard deps are Mnemosyne and `cryptography`; adding a third-party dep needs a good reason.

---

## License

[MIT](./LICENSE) © 2026 Christian Knopp.

---

## Acknowledgements

- **[Mnemosyne](https://github.com/Zynerji/Mnemosyne)** for the deterministic Knowledge Asset substrate Harmonia builds on.
- **[OriginTrail](https://origintrail.io/)** for the Decentralized Knowledge Graph specification and the `dkg.py` SDK that makes on-chain anchoring practical.
- **[cryptography](https://cryptography.io/)** for a serious, auditable Ed25519 implementation in Python.
- The goddess Harmonia, daughter of Ares and Aphrodite — for the reminder that concord is a product of two very different forces agreeing to stand side by side.
