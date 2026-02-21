"""Shared test fixtures for the Multi-Regime Trading Stack."""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Add engine to path
ENGINE_DIR = str(Path(__file__).parent.parent / "engine")
sys.path.insert(0, ENGINE_DIR)

SAMPLE_MODEL = {
    "schema_version": 2,
    "symbol": "NQ",
    "k": 3,
    "n_features": 6,
    "initial_probs": [0.4, 0.35, 0.25],
    "transition_matrix": [
        [0.8, 0.15, 0.05],
        [0.1, 0.8, 0.1],
        [0.05, 0.15, 0.8],
    ],
    "means": [
        [0.0, -0.5, 0.0, 0.0, 0.8, 0.0],
        [0.1, 0.0, 0.1, 0.2, 1.0, 0.1],
        [0.0, 0.5, -0.1, 0.0, 1.5, 0.0],
    ],
    "variances": [
        [0.5, 0.3, 0.2, 0.5, 0.3, 0.5],
        [1.0, 0.5, 0.3, 0.8, 0.5, 0.8],
        [2.0, 1.0, 0.5, 1.5, 1.0, 1.5],
    ],
    "feature_mean": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    "feature_std": [1.0, 1.0, 0.5, 1.0, 0.5, 1.0],
    "regime_labels": ["low_vol", "trending", "high_vol"],
    "metadata": {
        "trained_at": "2026-02-20T22:00:00Z",
        "training_bars": 10000,
        "log_likelihood": -25000.0,
        "converged": True,
        "n_iterations": 150,
        "random_restarts": 5,
        "data_start": "2024-01-01",
        "data_end": "2026-02-20",
    },
}


@pytest.fixture
def sample_model():
    return SAMPLE_MODEL.copy()


@pytest.fixture
def sample_model_file(tmp_path):
    path = tmp_path / "NQ_model.json"
    with open(path, "w") as f:
        json.dump(SAMPLE_MODEL, f)
    return str(path)


@pytest.fixture
def sample_model_dir(tmp_path):
    for sym in ["NQ", "ES"]:
        model = SAMPLE_MODEL.copy()
        model["symbol"] = sym
        path = tmp_path / f"{sym}_model.json"
        with open(path, "w") as f:
            json.dump(model, f)
    return str(tmp_path)


@pytest.fixture
def sample_bars():
    """Generate synthetic OHLCV bar data."""
    np.random.seed(42)
    n = 500
    close = 15000 + np.cumsum(np.random.randn(n) * 10)
    high = close + np.abs(np.random.randn(n) * 5)
    low = close - np.abs(np.random.randn(n) * 5)
    open_ = close + np.random.randn(n) * 3
    volume = np.abs(np.random.randn(n) * 1000 + 5000)

    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


@pytest.fixture
def sample_features():
    """Generate sample feature vectors."""
    np.random.seed(42)
    return np.random.randn(200, 6)
