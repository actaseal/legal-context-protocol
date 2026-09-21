# Disputed agent purchase -- verify-only sample

A real, signed policy-decision receipt (minted by ActaSeal's gateway,
committing to a merchant terms document's `terms_hash` inside its signed
payload) bound to an LCP record, re-verified here using **only**:

- this repo's own `lcp_actaseal_binding` package (loaded straight from
  `../../src`, no `pip install` needed), and
- a vendored, unmodified copy of ActaSeal's standalone receipt-signature
  verifier (`vendor/verify_receipt.py` -- see its header comment for the
  exact source commit hash).

No private ActaSeal-repo code, no network access, no ActaSeal product
installed anywhere. This is the sample referenced by the binding
profile's own PR #4 fix (`terms_hash` inside the signed receipt).

## Run it

From a fresh clone of this repo, with nothing beyond the Python standard
library and `cryptography`:

```
pip install cryptography
python examples/disputed_agent_purchase/verify_sample.py
```

### Expected output

Three scenarios, each printing a named verdict:

| # | Scenario | Verdict |
|---|----------|---------|
| 1 | real `terms.txt` against the receipt that committed to it | **PASS** |
| 2 | terms bytes swapped at verification time | **FAIL** -- `LCP_TERMS_HASH_MISMATCH` |
| 3 | a receipt minted **without** terms, but a record claims terms anyway | **FAIL** -- `LCP_TERMS_NOT_IN_SIGNED_RECEIPT` |

Exit code `0` when all three match their expected verdict, `1` otherwise.

Scenario 3 is the exact attack this binding profile exists to close
(reported by shunhe-wang on PR #4): replacing the terms document *and*
the record's claimed hash together used to produce a record that passed
every check, because nothing the signer signed committed to which terms
were in force.

## Files here

- `verify_sample.py` -- the only script; run it, nothing else needed
- `receipt.json` -- a signed receipt committing to `terms_hash`
- `receipt_without_terms.json` -- a signed receipt committing to no terms
- `terms.txt` -- the real terms-document bytes
- `manifest.json` -- the small binding manifest (`action_id` +
  `scope_conformance_headline`) the receipts were minted alongside
- `lcp_record.json` -- the LCP record binding `terms.txt` to `receipt.json`
- `receipt_public_key_hex.txt` -- the receipt signer's public key (hex)
- `vendor/verify_receipt.py` -- vendored, unmodified standalone
  receipt-signature verifier (see its header for the source commit)

All six data files were generated once, ahead of time, by ActaSeal's own
gateway against its shipped default policy (`support_refund_promise_policy`)
-- this directory only ever *verifies* them; nothing here mints receipts
or talks to the ActaSeal product.
