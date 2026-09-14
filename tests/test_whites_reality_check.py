"""Tests for White's Reality Check."""
import numpy as np
import pytest

from validation.whites_reality_check import (
    _stationary_block_indices,
    whites_reality_check,
)


# ---------------------------------------------------------------- bootstrap

def test_stationary_bootstrap_length():
    rng = np.random.default_rng(0)
    idx = _stationary_block_indices(T=1000, mean_block=20.0, rng=rng)
    assert len(idx) == 1000
    assert idx.min() >= 0
    assert idx.max() < 1000


def test_stationary_bootstrap_is_deterministic():
    idx1 = _stationary_block_indices(500, 20.0, np.random.default_rng(1))
    idx2 = _stationary_block_indices(500, 20.0, np.random.default_rng(1))
    assert np.array_equal(idx1, idx2)


# ---------------------------------------------------------------- RC behavior

def test_rc_high_p_value_for_pure_noise():
    """K columns of pure noise → no combo should be significant."""
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.01, size=(2000, 20))
    # No drift in any column
    r = whites_reality_check(F, n_bootstrap=500, seed=42)
    assert r["p_value"] > 0.05
    assert "FAIL TO REJECT" in r["interpretation"]


def test_rc_low_p_value_for_strong_alpha():
    """One column with strong drift should be detected."""
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.01, size=(2000, 20))
    # Inject a strong signal into column 5
    F[:, 5] += 0.002  # +0.2% per bar, huge
    r = whites_reality_check(F, n_bootstrap=500, seed=42)
    assert r["p_value"] < 0.05
    assert "REJECT" in r["interpretation"]


def test_rc_returns_all_expected_fields():
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.01, size=(500, 10))
    r = whites_reality_check(F, n_bootstrap=200, seed=42)
    for key in ["method", "n_bootstrap", "T", "K", "mean_block",
                "V_observed", "best_combo", "p_value",
                "V_bootstrap_mean", "V_bootstrap_std",
                "V_bootstrap_p95", "V_bootstrap_p99",
                "top_5_combos", "interpretation"]:
        assert key in r, f"missing key {key}"
    assert len(r["top_5_combos"]) == 5
    assert r["T"] == 500
    assert r["K"] == 10


def test_rc_rejects_nans():
    F = np.random.default_rng(0).normal(0, 0.01, size=(500, 10))
    F[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        whites_reality_check(F, n_bootstrap=100)


def test_rc_rejects_wrong_shape():
    with pytest.raises(ValueError, match="2D"):
        whites_reality_check(np.zeros(100))


def test_rc_deterministic():
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.01, size=(500, 10))
    r1 = whites_reality_check(F, n_bootstrap=200, seed=42)
    r2 = whites_reality_check(F, n_bootstrap=200, seed=42)
    assert r1["p_value"] == r2["p_value"]


def test_rc_labels_used():
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.01, size=(500, 3))
    F[:, 1] += 0.01  # column 1 wins
    labels = ["AAA", "BBB", "CCC"]
    r = whites_reality_check(F, n_bootstrap=200, seed=42, combo_labels=labels)
    assert r["best_combo"] == "BBB"