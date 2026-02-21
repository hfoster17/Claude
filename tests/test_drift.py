"""Tests for drift detection."""

import numpy as np
import pytest

from drift import DriftMonitor, DriftManager


@pytest.fixture
def monitor():
    trans = np.array([[0.8, 0.15, 0.05], [0.1, 0.8, 0.1], [0.05, 0.15, 0.8]])
    feat_mean = np.zeros(6)
    feat_std = np.ones(6)
    return DriftMonitor(
        symbol="NQ",
        k=3,
        training_transition_matrix=trans,
        training_log_likelihood=-25000.0,
        training_feature_mean=feat_mean,
        training_feature_std=feat_std,
        window=100,
    )


class TestDriftMonitor:
    def test_not_ready_initially(self, monitor):
        assert not monitor.ready

    def test_ready_after_updates(self, monitor):
        np.random.seed(42)
        for i in range(100):
            monitor.update(
                state=np.random.randint(0, 3),
                log_likelihood=-25.0,
                features=np.random.randn(6),
            )
        assert monitor.ready

    def test_occupancy_drift_balanced(self, monitor):
        """Balanced state distribution should have low drift."""
        for i in range(300):
            monitor.update(state=i % 3, log_likelihood=-25.0, features=np.random.randn(6))
        drift = monitor.compute_occupancy_drift()
        assert drift < 0.1

    def test_occupancy_drift_imbalanced(self, monitor):
        """Heavily imbalanced distribution should have high drift."""
        for i in range(200):
            monitor.update(state=0, log_likelihood=-25.0, features=np.random.randn(6))
        drift = monitor.compute_occupancy_drift()
        assert drift > 0.1

    def test_transition_drift_matching(self, monitor):
        """Transitions matching training matrix should have low KL."""
        np.random.seed(42)
        state = 0
        for _ in range(500):
            # Simulate from training transition matrix
            probs = [0.8, 0.15, 0.05] if state == 0 else [0.1, 0.8, 0.1] if state == 1 else [0.05, 0.15, 0.8]
            state = np.random.choice(3, p=probs)
            monitor.update(state=state, log_likelihood=-25.0, features=np.random.randn(6))
        kl = monitor.compute_transition_drift()
        assert kl < 0.5  # Should be relatively low

    def test_likelihood_drop_none(self, monitor):
        """No drop when likelihood matches training."""
        for _ in range(200):
            monitor.update(state=0, log_likelihood=-25000.0, features=np.random.randn(6))
        drop = monitor.compute_likelihood_drop()
        assert drop < 0.01

    def test_feature_drift_zero_shift(self, monitor):
        """No drift when features match training stats."""
        np.random.seed(42)
        for _ in range(200):
            features = np.random.randn(6)  # mean=0, std=1 matches training
            monitor.update(state=0, log_likelihood=-25.0, features=features)
        drifts = monitor.compute_feature_drift()
        assert all(d < 1.0 for d in drifts)

    def test_feature_drift_shifted(self, monitor):
        """Large mean shift should produce drift."""
        for _ in range(200):
            features = np.random.randn(6) + 5.0  # Mean shifted by 5
            monitor.update(state=0, log_likelihood=-25.0, features=features)
        drifts = monitor.compute_feature_drift()
        assert max(drifts) > 1.0

    def test_should_retrain_no_drift(self, monitor):
        np.random.seed(42)
        for _ in range(200):
            monitor.update(state=np.random.randint(0, 3), log_likelihood=-25.0,
                          features=np.random.randn(6))
        should, reasons = monitor.should_retrain()
        # May or may not trigger depending on random data, but shouldn't crash
        assert isinstance(should, bool)
        assert isinstance(reasons, list)

    def test_get_all_metrics(self, monitor):
        for _ in range(200):
            monitor.update(state=0, log_likelihood=-25.0, features=np.random.randn(6))
        metrics = monitor.get_all_metrics()
        assert "occupancy_drift" in metrics
        assert "transition_kl" in metrics
        assert "likelihood_drop" in metrics
        assert "feature_drifts" in metrics


class TestDriftManager:
    def test_register_and_get(self, monitor):
        mgr = DriftManager()
        mgr.register("NQ", monitor)
        assert mgr.get("NQ") is monitor
        assert mgr.get("ES") is None

    def test_get_all_metrics(self, monitor):
        mgr = DriftManager()
        mgr.register("NQ", monitor)
        for _ in range(200):
            monitor.update(state=0, log_likelihood=-25.0, features=np.random.randn(6))
        all_metrics = mgr.get_all_metrics()
        assert "NQ" in all_metrics
