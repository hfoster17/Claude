"""
Drift Detection — monitors model drift across multiple dimensions.

Metrics:
  1. State occupancy drift (chi-squared)
  2. Transition drift (KL divergence)
  3. Likelihood drop (rolling vs training baseline)
  4. Feature distribution drift (per-feature KS test)
"""

import logging
import math
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DriftMonitor:
    """Monitors drift for a single symbol's HMM model."""

    def __init__(
        self,
        symbol: str,
        k: int,
        training_transition_matrix: np.ndarray,
        training_log_likelihood: float,
        training_feature_mean: np.ndarray,
        training_feature_std: np.ndarray,
        window: int = 500,
    ):
        self.symbol = symbol
        self.k = k
        self.window = window

        # Training baselines
        self._train_trans = np.array(training_transition_matrix)
        self._train_ll = training_log_likelihood
        self._train_feat_mean = np.array(training_feature_mean)
        self._train_feat_std = np.array(training_feature_std)

        # Rolling buffers
        self._state_history: deque = deque(maxlen=window)
        self._ll_history: deque = deque(maxlen=window)
        self._feature_history: deque = deque(maxlen=window)

        # Thresholds
        self.occupancy_threshold = 0.3
        self.transition_kl_threshold = 0.5
        self.likelihood_drop_threshold = 0.2
        self.feature_ks_threshold = 0.15

    def update(self, state: int, log_likelihood: float, features: np.ndarray) -> None:
        """Record one observation."""
        self._state_history.append(state)
        self._ll_history.append(log_likelihood)
        self._feature_history.append(features.copy())

    @property
    def ready(self) -> bool:
        return len(self._state_history) >= min(100, self.window)

    def compute_occupancy_drift(self) -> float:
        """
        Chi-squared-like metric comparing observed state occupancy vs uniform expectation.
        Returns value in [0, inf). Higher = more drift.
        """
        if not self.ready:
            return 0.0

        counts = np.zeros(self.k)
        for s in self._state_history:
            if 0 <= s < self.k:
                counts[s] += 1

        n = len(self._state_history)
        expected = n / self.k  # uniform baseline

        if expected == 0:
            return 0.0

        chi2 = np.sum((counts - expected) ** 2 / expected) / self.k
        return float(chi2)

    def compute_transition_drift(self) -> float:
        """
        KL divergence between observed transition frequencies and training transition matrix.
        Returns value in [0, inf). Higher = more drift.
        """
        if len(self._state_history) < 10:
            return 0.0

        # Count observed transitions
        obs_trans = np.zeros((self.k, self.k))
        history = list(self._state_history)
        for i in range(len(history) - 1):
            s_from = history[i]
            s_to = history[i + 1]
            if 0 <= s_from < self.k and 0 <= s_to < self.k:
                obs_trans[s_from, s_to] += 1

        # Normalize rows
        row_sums = obs_trans.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1.0)
        obs_freq = obs_trans / row_sums

        # KL divergence: sum over all (i,j)
        eps = 1e-10
        p = np.clip(obs_freq, eps, 1.0)
        q = np.clip(self._train_trans, eps, 1.0)

        kl = np.sum(p * np.log(p / q)) / self.k
        return float(max(kl, 0.0))

    def compute_likelihood_drop(self) -> float:
        """
        Fractional drop in rolling log-likelihood vs training baseline.
        Returns value in [0, 1]. Higher = worse.
        """
        if not self._ll_history:
            return 0.0

        rolling_avg = np.mean(list(self._ll_history))

        if self._train_ll == 0:
            return 0.0

        # Normalize per-bar
        n_train = max(1, abs(self._train_ll))
        drop = (self._train_ll - rolling_avg) / n_train

        return float(max(min(drop, 1.0), 0.0))

    def compute_feature_drift(self) -> List[float]:
        """
        Per-feature KS-like statistic comparing rolling distribution vs training stats.
        Returns list of drift values per feature.
        """
        if len(self._feature_history) < 30:
            return [0.0] * len(self._train_feat_mean)

        features = np.array(list(self._feature_history))
        n_features = features.shape[1]
        drifts = []

        for i in range(n_features):
            col = features[:, i]
            obs_mean = np.mean(col)
            obs_std = max(np.std(col, ddof=1), 1e-10)
            train_std = max(self._train_feat_std[i], 1e-10)

            # Simplified KS: normalized mean shift + variance ratio
            mean_shift = abs(obs_mean - self._train_feat_mean[i]) / train_std
            var_ratio = abs(math.log(obs_std / train_std)) if train_std > 0 else 0
            drift_val = 0.7 * mean_shift + 0.3 * var_ratio

            drifts.append(round(float(drift_val), 4))

        return drifts

    def get_all_metrics(self) -> Dict:
        """Compute and return all drift metrics."""
        feature_drifts = self.compute_feature_drift()
        max_feature_drift = max(feature_drifts) if feature_drifts else 0.0

        metrics = {
            "symbol": self.symbol,
            "window_size": len(self._state_history),
            "ready": self.ready,
            "occupancy_drift": round(self.compute_occupancy_drift(), 4),
            "transition_kl": round(self.compute_transition_drift(), 4),
            "likelihood_drop": round(self.compute_likelihood_drop(), 4),
            "feature_drifts": feature_drifts,
            "max_feature_drift": round(max_feature_drift, 4),
        }

        return metrics

    def should_retrain(self) -> Tuple[bool, List[str]]:
        """Check if drift thresholds are exceeded. Returns (should_retrain, reasons)."""
        if not self.ready:
            return False, []

        reasons = []

        occ = self.compute_occupancy_drift()
        if occ > self.occupancy_threshold:
            reasons.append(f"occupancy_drift={occ:.4f} > {self.occupancy_threshold}")

        trans_kl = self.compute_transition_drift()
        if trans_kl > self.transition_kl_threshold:
            reasons.append(f"transition_kl={trans_kl:.4f} > {self.transition_kl_threshold}")

        ll_drop = self.compute_likelihood_drop()
        if ll_drop > self.likelihood_drop_threshold:
            reasons.append(f"likelihood_drop={ll_drop:.4f} > {self.likelihood_drop_threshold}")

        feat_drifts = self.compute_feature_drift()
        for i, d in enumerate(feat_drifts):
            if d > self.feature_ks_threshold:
                reasons.append(f"feature_{i}_drift={d:.4f} > {self.feature_ks_threshold}")
                break  # One feature enough to trigger

        return len(reasons) > 0, reasons


class DriftManager:
    """Manages drift monitors for all symbols."""

    def __init__(self):
        self._monitors: Dict[str, DriftMonitor] = {}

    def register(self, symbol: str, monitor: DriftMonitor) -> None:
        self._monitors[symbol] = monitor
        logger.info("Registered drift monitor for %s", symbol)

    def get(self, symbol: str) -> Optional[DriftMonitor]:
        return self._monitors.get(symbol)

    def get_all_metrics(self) -> Dict[str, Dict]:
        return {sym: mon.get_all_metrics() for sym, mon in self._monitors.items()}

    def check_all_retrain(self) -> Dict[str, Tuple[bool, List[str]]]:
        return {sym: mon.should_retrain() for sym, mon in self._monitors.items()}
