#!/usr/bin/env python3
"""Verify-only sample: re-checks a disputed-purchase LCP binding using
ONLY this repo's own standalone `lcp_actaseal_binding` package (loaded
straight from ../../src, no `pip install` required) plus a vendored,
unmodified copy of ActaSeal's standalone receipt-signature verifier
(vendor/verify_receipt.py -- see its header for the exact source
commit). No private-repo code, no network access, no ActaSeal product
installed anywhere.

Works from a fresh clone of this repo with nothing beyond the Python
standard library and the third-party `cryptography` package:

    pip install cryptography
    python examples/disputed_agent_purchase/verify_sample.py

Reads the six sample files sitting alongside this script (receipt.json,
receipt_without_terms.json, terms.txt, manifest.json, lcp_record.json,
receipt_public_key_hex.txt -- see README.md for what each one is) and
runs three scenarios, printing a named verdict for each:

  1. real terms.txt against the receipt that committed to it  -> PASS
  2. terms bytes swapped at verification time                 -> FAIL LCP_TERMS_HASH_MISMATCH
  3. a receipt minted WITHOUT terms, record claims terms anyway -> FAIL LCP_TERMS_NOT_IN_SIGNED_RECEIPT

Exit code 0 when all three scenarios match their expected verdict,
1 otherwise.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PACKAGE_SRC = HERE.parent.parent / "src"
VENDOR_VERIFY_RECEIPT = HERE / "vendor" / "verify_receipt.py"

# Load lcp_actaseal_binding straight from source -- no `pip install`
# needed, so this genuinely runs from a bare fresh clone.
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from lcp_actaseal_binding import (  # noqa: E402
    LCP_TERMS_HASH_MISMATCH,
    LCP_TERMS_NOT_IN_SIGNED_RECEIPT,
    build_lcp_record,
    verify_lcp_record,
)


def _load_vendored_verify_receipt():
    spec = importlib.util.spec_from_file_location("vendored_verify_receipt", VENDOR_VERIFY_RECEIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_namespace(receipt_dict: dict) -> SimpleNamespace:
    """Any object exposing the right attributes satisfies
    lcp_actaseal_binding's structural PolicyReceipt protocol -- no
    ActaSeal class required."""
    return SimpleNamespace(
        decision=receipt_dict["decision"],
        reason_code=receipt_dict["reason_code"],
        action_hash=receipt_dict["action_hash"],
        evidence_set_hash=receipt_dict["evidence_set_hash"],
        ledger_entry_hash=receipt_dict["ledger_entry_hash"],
        timestamp=receipt_dict["timestamp"],
        signature=receipt_dict["signature"],
        mandate_hash=receipt_dict.get("mandate_hash"),
        terms_hash=receipt_dict.get("terms_hash"),
    )


def main(sample_dir: Path) -> int:
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_der_public_key
    except ImportError:
        print("UNABLE_TO_RUN: the 'cryptography' package is required (pip install cryptography)")
        return 2

    verify_receipt = _load_vendored_verify_receipt()
    crypto = {
        "ed25519_public_key_cls": Ed25519PublicKey,
        "invalid_signature_error": InvalidSignature,
        "unsupported_algorithm_error": UnsupportedAlgorithm,
        "load_der_public_key": load_der_public_key,
        "ecdsa_sha256": ec.ECDSA(hashes.SHA256()),
    }

    receipt_dict = json.loads((sample_dir / "receipt.json").read_text())
    receipt_without_terms_dict = json.loads((sample_dir / "receipt_without_terms.json").read_text())
    manifest = json.loads((sample_dir / "manifest.json").read_text())
    lcp_record = json.loads((sample_dir / "lcp_record.json").read_text())
    real_terms = (sample_dir / "terms.txt").read_bytes()
    public_key_hex = (sample_dir / "receipt_public_key_hex.txt").read_text().strip()

    def verify_receipt_signature(receipt_ns: SimpleNamespace) -> bool:
        source = receipt_dict if receipt_ns.signature == receipt_dict["signature"] else receipt_without_terms_dict
        failures: list[str] = []
        verify_receipt.verify_signature(source, public_key_hex, failures, crypto)
        return not failures

    receipt_ns = _receipt_namespace(receipt_dict)
    receipt_without_terms_ns = _receipt_namespace(receipt_without_terms_dict)

    all_ok = True

    print("=" * 72)
    print("Scenario 1: real terms.txt against the receipt that committed to it")
    print("=" * 72)
    failures = verify_lcp_record(
        lcp_record, receipt=receipt_ns, manifest=manifest,
        verify_receipt_signature=verify_receipt_signature, terms_document=real_terms,
    )
    if not failures:
        print("VERDICT: PASS -- terms bound to the signed receipt verify cleanly.\n")
    else:
        print(f"VERDICT: FAIL (unexpected) -- {failures}\n")
        all_ok = False

    print("=" * 72)
    print("Scenario 2: swap the terms bytes at verification time")
    print("=" * 72)
    swapped_terms = real_terms.replace(b"30 days", b"3 days")
    assert swapped_terms != real_terms
    failures = verify_lcp_record(
        lcp_record, receipt=receipt_ns, manifest=manifest,
        verify_receipt_signature=verify_receipt_signature, terms_document=swapped_terms,
    )
    named = [f.split(":")[0] for f in failures]
    if LCP_TERMS_HASH_MISMATCH in named:
        print(f"VERDICT: FAIL as expected -- {LCP_TERMS_HASH_MISMATCH}")
        print(f"  detail: {[f for f in failures if f.startswith(LCP_TERMS_HASH_MISMATCH)][0]}\n")
    else:
        print(f"VERDICT: UNEXPECTED -- expected {LCP_TERMS_HASH_MISMATCH}, got {failures}\n")
        all_ok = False

    print("=" * 72)
    print("Scenario 3: a receipt minted WITHOUT terms, record claims terms anyway")
    print("=" * 72)
    record_over_untermed_receipt = build_lcp_record(
        receipt=receipt_without_terms_ns, manifest=manifest,
        terms_url="https://merchant.example/terms/disputed-purchase.txt",
        terms_document=real_terms, terms_format="text/plain",
    )
    failures = verify_lcp_record(
        record_over_untermed_receipt, receipt=receipt_without_terms_ns, manifest=manifest,
        verify_receipt_signature=verify_receipt_signature, terms_document=real_terms,
    )
    named = [f.split(":")[0] for f in failures]
    if named == [LCP_TERMS_NOT_IN_SIGNED_RECEIPT]:
        print(f"VERDICT: FAIL as expected -- {LCP_TERMS_NOT_IN_SIGNED_RECEIPT}")
        print(f"  detail: {failures[0]}\n")
    else:
        print(f"VERDICT: UNEXPECTED -- expected exactly [{LCP_TERMS_NOT_IN_SIGNED_RECEIPT}], got {failures}\n")
        all_ok = False

    if all_ok:
        print("All three scenarios matched their expected verdicts.")
        return 0
    print("One or more scenarios did NOT match their expected verdict.")
    return 1


if __name__ == "__main__":
    sys.exit(main(HERE))
