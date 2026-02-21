"""Tests for feature_engine.py — feature calculation correctness."""

import math
import numpy as np
import pytest

from feature_engine import FeatureEngine, compute_features_batch, N_FEATURES, RollingStats


class TestRollingStats:
    def test_empty(self):
        rs = RollingStats(10)
        assert rs.mean() == 0.0
        assert rs.std() == 0.0
        assert rs.count == 0

    def test_single_value(self):
        rs = RollingStats(10)
        rs.push(5.0)
        assert rs.mean() == 5.0
        assert rs.std() == 0.0

    def test_basic_stats(self):
        rs = RollingStats(100)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            rs.push(v)
        assert abs(rs.mean() - 3.0) < 1e-10
        assert abs(rs.std() - math.sqrt(2.5)) < 1e-10

    def test_window_cap(self):
        rs = RollingStats(3)
        for v in [1, 2, 3, 4, 5]:
            rs.push(v)
        assert rs.count == 3
        assert abs(rs.mean() - 4.0) < 1e-10


class TestFeatureEngine:
    def test_output_shape(self, sample_bars):
        engine = FeatureEngine()
        for i in range(len(sample_bars["close"])):
            features = engine.update(
                sample_bars["open"][i],
                sample_bars["high"][i],
                sample_bars["low"][i],
                sample_bars["close"][i],
                sample_bars["volume"][i],
            )
            assert features.shape == (N_FEATURES,)

    def test_no_nan(self, sample_bars):
        engine = FeatureEngine()
        for i in range(len(sample_bars["close"])):
            features = engine.update(
                sample_bars["open"][i],
                sample_bars["high"][i],
                sample_bars["low"][i],
                sample_bars["close"][i],
                sample_bars["volume"][i],
            )
            assert not np.any(np.isnan(features)), f"NaN at bar {i}: {features}"
            assert not np.any(np.isinf(features)), f"Inf at bar {i}: {features}"

    def test_ready_after_warmup(self, sample_bars):
        engine = FeatureEngine()
        for i in range(99):
            engine.update(
                sample_bars["open"][i], sample_bars["high"][i],
                sample_bars["low"][i], sample_bars["close"][i],
                sample_bars["volume"][i],
            )
        assert not engine.ready

        engine.update(
            sample_bars["open"][99], sample_bars["high"][99],
            sample_bars["low"][99], sample_bars["close"][99],
            sample_bars["volume"][99],
        )
        assert engine.ready

    def test_rsi_deviation_bounded(self, sample_bars):
        engine = FeatureEngine()
        for i in range(len(sample_bars["close"])):
            features = engine.update(
                sample_bars["open"][i], sample_bars["high"][i],
                sample_bars["low"][i], sample_bars["close"][i],
                sample_bars["volume"][i],
            )
            assert -1.0 <= features[2] <= 1.0, f"RSI dev out of bounds: {features[2]}"

    def test_clipped_features_bounded(self, sample_bars):
        engine = FeatureEngine()
        for i in range(len(sample_bars["close"])):
            features = engine.update(
                sample_bars["open"][i], sample_bars["high"][i],
                sample_bars["low"][i], sample_bars["close"][i],
                sample_bars["volume"][i],
            )
            assert -3.0 <= features[3] <= 3.0, f"VWAP dist out of bounds: {features[3]}"
            assert 0.0 <= features[4] <= 5.0, f"Bar range out of bounds: {features[4]}"
            assert -3.0 <= features[5] <= 3.0, f"Vol zscore out of bounds: {features[5]}"

    def test_zero_volume(self):
        engine = FeatureEngine()
        for i in range(200):
            features = engine.update(100 + i * 0.1, 101, 99, 100 + i * 0.1, 0.0)
        assert not np.any(np.isnan(features))

    def test_flat_price(self):
        engine = FeatureEngine()
        for i in range(200):
            features = engine.update(100, 100, 100, 100, 1000)
        assert not np.any(np.isnan(features))

    def test_session_reset(self, sample_bars):
        engine = FeatureEngine()
        for i in range(50):
            engine.update(
                sample_bars["open"][i], sample_bars["high"][i],
                sample_bars["low"][i], sample_bars["close"][i],
                sample_bars["volume"][i],
            )

        engine.update(
            sample_bars["open"][50], sample_bars["high"][50],
            sample_bars["low"][50], sample_bars["close"][50],
            sample_bars["volume"][50], session_reset=True,
        )
        # After reset, VWAP should be based on single bar
        assert not np.any(np.isnan(engine.get_features()))


class TestBatchFeatures:
    def test_batch_matches_sequential(self, sample_bars):
        n = len(sample_bars["close"])
        batch = compute_features_batch(
            sample_bars["open"], sample_bars["high"],
            sample_bars["low"], sample_bars["close"],
            sample_bars["volume"],
        )
        assert batch.shape == (n, N_FEATURES)

        engine = FeatureEngine()
        for i in range(n):
            seq_feat = engine.update(
                sample_bars["open"][i], sample_bars["high"][i],
                sample_bars["low"][i], sample_bars["close"][i],
                sample_bars["volume"][i],
            )
            np.testing.assert_allclose(batch[i], seq_feat, atol=1e-10,
                                       err_msg=f"Mismatch at bar {i}")
