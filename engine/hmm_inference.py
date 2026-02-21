"""
HMM Inference — scaled forward algorithm for online regime detection.
Mirrors the internal HMM filter in the NT8 strategy.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

VARIANCE_FLOOR = 1e-6
LOG_ZERO = -1e30


class HMMModel:
    """Holds a loaded Gaussian HMM model."""

    def __init__(self, model_dict: Dict):
        self.symbol: str = model_dict["symbol"]
        self.k: int = model_dict["k"]
        self.n_features: int = model_dict["n_features"]
        self.schema_version: int = model_dict["schema_version"]

        self.initial_probs: np.ndarray = np.array(model_dict["initial_probs"], dtype=np.float64)
        self.transition_matrix: np.ndarray = np.array(model_dict["transition_matrix"], dtype=np.float64)
        self.means: np.ndarray = np.array(model_dict["means"], dtype=np.float64)
        self.variances: np.ndarray = np.array(model_dict["variances"], dtype=np.float64)
        self.feature_mean: np.ndarray = np.array(model_dict["feature_mean"], dtype=np.float64)
        self.feature_std: np.ndarray = np.array(model_dict["feature_std"], dtype=np.float64)
        self.regime_labels: List[str] = model_dict["regime_labels"]
        self.metadata: Dict = model_dict.get("metadata", {})

        # Apply variance floor
        self.variances = np.maximum(self.variances, VARIANCE_FLOOR)

        # Validate dimensions
        assert self.initial_probs.shape == (self.k,)
        assert self.transition_matrix.shape == (self.k, self.k)
        assert self.means.shape == (self.k, self.n_features)
        assert self.variances.shape == (self.k, self.n_features)


class HMMFilter:
    """
    Online HMM filter using the scaled forward algorithm.
    Processes one observation at a time, maintaining filtered state probabilities.
    """

    def __init__(self, model: HMMModel):
        self.model = model
        self._alpha: np.ndarray = model.initial_probs.copy()
        self._log_likelihood: float = 0.0
        self._step_count: int = 0

    def reset(self) -> None:
        """Reset filter to initial state."""
        self._alpha = self.model.initial_probs.copy()
        self._log_likelihood = 0.0
        self._step_count = 0

    @property
    def state_probs(self) -> np.ndarray:
        return self._alpha.copy()

    @property
    def dominant_state(self) -> int:
        return int(np.argmax(self._alpha))

    @property
    def confidence(self) -> float:
        return float(np.max(self._alpha))

    @property
    def log_likelihood(self) -> float:
        return self._log_likelihood

    def _gaussian_pdf(self, obs: np.ndarray, mean: np.ndarray, var: np.ndarray) -> float:
        """
        Compute multivariate Gaussian PDF with diagonal covariance.
        Uses log-space to avoid underflow.
        """
        n = len(obs)
        log_det = np.sum(np.log(var))
        diff = obs - mean
        mahal = np.sum(diff ** 2 / var)
        log_pdf = -0.5 * (n * math.log(2 * math.pi) + log_det + mahal)
        return log_pdf

    def update(self, observation: np.ndarray) -> Tuple[np.ndarray, int, float]:
        """
        Process one observation vector. Returns (state_probs, dominant_state, confidence).

        Uses the scaled forward algorithm:
        1. Predict: alpha_pred[j] = sum_i(alpha[i] * A[i,j])
        2. Update: alpha[j] = alpha_pred[j] * emission(obs|j)
        3. Normalize: alpha = alpha / sum(alpha)
        """
        k = self.model.k
        obs = np.asarray(observation, dtype=np.float64)

        # Compute emission log-likelihoods for each state
        log_emissions = np.zeros(k)
        for j in range(k):
            log_emissions[j] = self._gaussian_pdf(
                obs, self.model.means[j], self.model.variances[j]
            )

        # Predict step: apply transition matrix
        alpha_pred = self._alpha @ self.model.transition_matrix

        # Update step: multiply by emissions (in log space for stability)
        log_alpha_pred = np.log(np.maximum(alpha_pred, 1e-300))
        log_alpha_new = log_alpha_pred + log_emissions

        # Normalize using log-sum-exp
        max_log = np.max(log_alpha_new)
        if max_log > LOG_ZERO:
            log_sum = max_log + math.log(np.sum(np.exp(log_alpha_new - max_log)))
            self._alpha = np.exp(log_alpha_new - log_sum)
            self._log_likelihood += log_sum
        else:
            # Complete underflow — reset to uniform
            self._alpha = np.ones(k) / k
            self._log_likelihood += LOG_ZERO

        # Safety: ensure probabilities sum to 1
        alpha_sum = np.sum(self._alpha)
        if alpha_sum > 0 and np.isfinite(alpha_sum):
            self._alpha /= alpha_sum
        else:
            self._alpha = np.ones(k) / k

        self._step_count += 1

        return self._alpha.copy(), self.dominant_state, self.confidence

    def batch_forward(self, observations: np.ndarray) -> np.ndarray:
        """
        Run forward algorithm on a batch of observations.
        Returns (n_obs, k) array of filtered state probabilities.
        """
        n = len(observations)
        all_probs = np.zeros((n, self.model.k))
        self.reset()

        for t in range(n):
            probs, _, _ = self.update(observations[t])
            all_probs[t] = probs

        return all_probs


def viterbi(model: HMMModel, observations: np.ndarray) -> np.ndarray:
    """
    Viterbi algorithm — most likely state sequence.
    Used for training labeling, not live trading.
    """
    n = len(observations)
    k = model.k
    log_delta = np.full((n, k), LOG_ZERO)
    psi = np.zeros((n, k), dtype=int)

    # Initialize
    for j in range(k):
        log_emit = _log_gaussian(observations[0], model.means[j], model.variances[j])
        log_delta[0, j] = math.log(max(model.initial_probs[j], 1e-300)) + log_emit

    # Forward pass
    log_trans = np.log(np.maximum(model.transition_matrix, 1e-300))
    for t in range(1, n):
        for j in range(k):
            log_emit = _log_gaussian(observations[t], model.means[j], model.variances[j])
            candidates = log_delta[t - 1] + log_trans[:, j]
            psi[t, j] = int(np.argmax(candidates))
            log_delta[t, j] = candidates[psi[t, j]] + log_emit

    # Backtrack
    states = np.zeros(n, dtype=int)
    states[-1] = int(np.argmax(log_delta[-1]))
    for t in range(n - 2, -1, -1):
        states[t] = psi[t + 1, states[t + 1]]

    return states


def _log_gaussian(obs: np.ndarray, mean: np.ndarray, var: np.ndarray) -> float:
    """Log of diagonal-covariance Gaussian PDF."""
    n = len(obs)
    log_det = np.sum(np.log(var))
    diff = obs - mean
    mahal = np.sum(diff ** 2 / var)
    return -0.5 * (n * math.log(2 * math.pi) + log_det + mahal)
