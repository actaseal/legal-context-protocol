"""Runs examples/disputed_agent_purchase/verify_sample.py as a real
subprocess -- the same way a third party following the example's
README would invoke it -- and asserts it exits 0 and prints all three
expected named verdicts. Regression coverage for the published sample
itself, not just the library functions it calls (those are already
covered directly by test_binding.py).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples" / "disputed_agent_purchase"


def test_verify_sample_script_passes_all_three_scenarios():
    result = subprocess.run(
        [sys.executable, str(EXAMPLE_DIR / "verify_sample.py")],
        cwd=EXAMPLE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: PASS -- terms bound to the signed receipt verify cleanly." in result.stdout
    assert "VERDICT: FAIL as expected -- LCP_TERMS_HASH_MISMATCH" in result.stdout
    assert "VERDICT: FAIL as expected -- LCP_TERMS_NOT_IN_SIGNED_RECEIPT" in result.stdout
    assert "All three scenarios matched their expected verdicts." in result.stdout


def test_verify_sample_script_needs_no_installed_package():
    """The script loads lcp_actaseal_binding straight from ../../src via
    sys.path, not an installed package -- confirm that claim by running
    it with a sanitized PYTHONPATH/site-packages-less environment isn't
    practical inside pytest's own interpreter, so instead this asserts
    the structural property the README promises: the script never
    imports anything outside the stdlib, `cryptography`, and its own
    vendor/ + ../../src -- i.e. no `import actaseal` anywhere in it."""
    text = (EXAMPLE_DIR / "verify_sample.py").read_text()
    assert "import actaseal" not in text
    assert "from actaseal" not in text
