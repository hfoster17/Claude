"""Tests for walk_forward.py — Walk-Forward HMM optimization."""

import numpy as np
import pytest

from walk_forward import (
    WalkForwardResult,
    WindowResult,
    _walk_forward_on_features,
    _compute_regime_stability,
    _get_regime_label,
)
from feature_engine import compute_features_batch


def _generate_synthetic_features(n_bars: int, seed: int = 42) -> np.ndarray:
    """
    Generate synthetic OHLCV data, compute features, and return the
    post-warmup valid feature array suitable for walk-forward testing.
    """
    np.random.seed(seed)
    close = 15000 + np.cumsum(np.random.randn(n_bars) * 10)
    high = close + np.abs(np.random.randn(n_bars) * 5)
    low = close - np.abs(np.random.randn(n_bars) * 5)
    open_ = close + np.random.randn(n_bars) * 3
    volume = np.abs(np.random.randn(n_bars) * 1000 + 5000)

    features = compute_features_batch(open_, high, low, close, volume)

    # Skip warmup
    warmup = 100
    features = features[warmup:]

    # Remove NaN rows
    valid_mask = ~np.any(np.isnan(features), axis=1)
    features = features[valid_mask]

    return features


class TestWalkForwardBasic:
    def test_walk_forward_basic(self):
        """Verify WalkForwardResult fields are populated correctly."""
        features = _generate_synthetic_features(3000, seed=42)

        result = _walk_forward_on_features(
            features,
            train_bars=500,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )

        assert isinstance(result, WalkForwardResult)
        assert result.total_windows > 0
        assert len(result.windows) == result.total_windows
        assert isinstance(result.aggregate_test_ll, float)
        assert isinstance(result.stability_score, float)

        # Check individual window fields
        for w in result.windows:
            assert isinstance(w, WindowResult)
            assert isinstance(w.window_idx, int)
            assert isinstance(w.train_start, int)
            assert isinstance(w.train_end, int)
            assert isinstance(w.test_start, int)
            assert isinstance(w.test_end, int)
            assert isinstance(w.train_ll, float)
            assert isinstance(w.test_ll, float)
            assert isinstance(w.regime_stability, float)
            assert isinstance(w.dominant_regime, str)

            # Stability must be in [0, 1]
            assert 0.0 <= w.regime_stability <= 1.0

            # Train/test boundaries should be contiguous
            assert w.test_start == w.train_end
            assert w.test_end > w.test_start

    def test_log_likelihoods_finite(self):
        """All log-likelihoods should be finite (not NaN or Inf)."""
        features = _generate_synthetic_features(3000, seed=42)

        result = _walk_forward_on_features(
            features,
            train_bars=500,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )

        for w in result.windows:
            assert np.isfinite(w.train_ll), f"Window {w.window_idx} train_ll is not finite"
            assert np.isfinite(w.test_ll), f"Window {w.window_idx} test_ll is not finite"

        assert np.isfinite(result.aggregate_test_ll)


class TestInsufficientData:
    def test_insufficient_data(self):
        """Should handle gracefully when data is too short for even one window."""
        features = _generate_synthetic_features(300, seed=42)

        result = _walk_forward_on_features(
            features,
            train_bars=2000,
            test_bars=500,
            step_bars=500,
            k=2,
            n_restarts=2,
        )

        assert isinstance(result, WalkForwardResult)
        assert result.total_windows == 0
        assert len(result.windows) == 0
        assert result.aggregate_test_ll == 0.0
        assert result.stability_score == 0.0

    def test_barely_insufficient(self):
        """Data just barely too short should produce zero windows."""
        # Need train_bars + test_bars = 500, provide 499 features
        features = np.random.randn(499, 6)

        result = _walk_forward_on_features(
            features,
            train_bars=300,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )

        # Should produce at least one window (499 >= 300 + 200 = 500 is False)
        assert result.total_windows == 0


class TestWindowCount:
    def test_window_count(self):
        """Verify correct number of windows are generated."""
        features = _generate_synthetic_features(4000, seed=42)
        n = len(features)

        train_bars = 500
        test_bars = 200
        step_bars = 200

        # Expected windows: start from 0, step by 200, while start + 700 <= n
        expected_windows = 0
        start = 0
        while start + train_bars + test_bars <= n:
            expected_windows += 1
            start += step_bars

        result = _walk_forward_on_features(
            features,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            k=2,
            n_restarts=2,
        )

        assert result.total_windows == expected_windows

    def test_window_indices_sequential(self):
        """Window indices should be sequential starting from 0."""
        features = _generate_synthetic_features(3000, seed=42)

        result = _walk_forward_on_features(
            features,
            train_bars=500,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )

        for i, w in enumerate(result.windows):
            assert w.window_idx == i


class TestDeterministic:
    def test_deterministic(self):
        """Same data should produce same results (HMM uses fixed random_state)."""
        features = _generate_synthetic_features(3000, seed=42)

        result1 = _walk_forward_on_features(
            features,
            train_bars=500,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )
        result2 = _walk_forward_on_features(
            features,
            train_bars=500,
            test_bars=200,
            step_bars=200,
            k=2,
            n_restarts=2,
        )

        assert result1.total_windows == result2.total_windows
        assert result1.aggregate_test_ll == pytest.approx(result2.aggregate_test_ll, rel=1e-6)
        assert result1.stability_score == pytest.approx(result2.stability_score, rel=1e-6)

        for w1, w2 in zip(result1.windows, result2.windows):
            assert w1.train_ll == pytest.approx(w2.train_ll, rel=1e-6)
            assert w1.test_ll == pytest.approx(w2.test_ll, rel=1e-6)
            assert w1.regime_stability == pytest.approx(w2.regime_stability, rel=1e-6)
            assert w1.dominant_regime == w2.dominant_regime


class TestSingleWindow:
    def test_single_window(self):
        """Minimum case with just enough data for exactly one window."""
        train_bars = 300
        test_bars = 100
        total = train_bars + test_bars

        features = _generate_synthetic_features(total + 200, seed=42)
        # Trim to exactly train + test bars
        features = features[:total]

        result = _walk_forward_on_features(
            features,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=test_bars,
            k=2,
            n_restarts=2,
        )

        assert result.total_windows == 1
        assert len(result.windows) == 1

        w = result.windows[0]
        assert w.window_idx == 0
        assert w.train_start == 0
        assert w.train_end == train_bars
        assert w.test_start == train_bars
        assert w.test_end == total

        # Aggregate should equal the single window values
        assert result.aggregate_test_ll == pytest.approx(w.test_ll, rel=1e-6)
        assert result.stability_score == pytest.approx(w.regime_stability, rel=1e-6)


class TestHelperFunctions:
    def test_regime_stability_all_same(self):
        """All same state should give stability = 1.0."""
        states = np.array([0, 0, 0, 0, 0])
        assert _compute_regime_stability(states) == 1.0

    def test_regime_stability_alternating(self):
        """Alternating states should give stability = 0.0."""
        states = np.array([0, 1, 0, 1, 0])
        assert _compute_regime_stability(states) == 0.0

    def test_regime_stability_single(self):
        """Single state should give stability = 1.0."""
        states = np.array([2])
        assert _compute_regime_stability(states) == 1.0

    def test_regime_label_k2(self):
        assert _get_regime_label(0, 2) == "low_vol"
        assert _get_regime_label(1, 2) == "high_vol"

    def test_regime_label_k3(self):
        assert _get_regime_label(0, 3) == "low_vol"
        assert _get_regime_label(1, 3) == "trending"
        assert _get_regime_label(2, 3) == "high_vol"

    def test_regime_label_k4(self):
        assert _get_regime_label(0, 4) == "state_0"
        assert _get_regime_label(3, 4) == "state_3"
