"""
Walk-Forward Optimizer — rolling train/test evaluation of HMM models.

Splits historical data into rolling train/test windows, trains a Gaussian HMM
on each training window, scores on the test window, and reports aggregate
out-of-sample performance and regime stability.

Usage:
    python walk_forward.py --symbol NQ
    python walk_forward.py --symbol NQ --train-bars 3000 --test-bars 500
    python walk_forward.py --symbol NQ --k 3 --n-restarts 5
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from data_pull import load_csv_data
from feature_engine import compute_features_batch

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """Results from a single walk-forward window."""

    window_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_ll: float
    test_ll: float
    regime_stability: float
    dominant_regime: str


@dataclass
class WalkForwardResult:
    """Aggregated results from walk-forward optimization."""

    windows: List[WindowResult] = field(default_factory=list)
    aggregate_test_ll: float = 0.0
    stability_score: float = 0.0
    total_windows: int = 0


def _train_hmm_window(
    features: np.ndarray,
    k: int = 3,
    n_restarts: int = 5,
    max_iter: int = 200,
    tol: float = 1e-4,
):
    """
    Train a Gaussian HMM on a feature window.
    Returns (model, best_score) or (None, -inf) on failure.
    """
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        logger.error("hmmlearn not installed. Run: pip install hmmlearn")
        return None, float("-inf")

    best_model = None
    best_score = float("-inf")

    for restart in range(n_restarts):
        try:
            model = GaussianHMM(
                n_components=k,
                covariance_type="diag",
                n_iter=max_iter,
                tol=tol,
                random_state=restart * 42 + 1,
                verbose=False,
            )
            model.fit(features)
            score = model.score(features)

            if score > best_score:
                best_score = score
                best_model = model
        except Exception as e:
            logger.debug("  Restart %d failed: %s", restart + 1, e)

    return best_model, best_score


def _compute_regime_stability(states: np.ndarray) -> float:
    """
    Compute regime stability: fraction of bars where regime didn't flip
    compared to the previous bar.
    """
    if len(states) <= 1:
        return 1.0

    stable_count = 0
    for i in range(1, len(states)):
        if states[i] == states[i - 1]:
            stable_count += 1

    return stable_count / (len(states) - 1)


def _get_regime_label(dominant_state: int, k: int) -> str:
    """Map state index to regime label."""
    if k == 2:
        labels = ["low_vol", "high_vol"]
    elif k == 3:
        labels = ["low_vol", "trending", "high_vol"]
    else:
        labels = [f"state_{i}" for i in range(k)]

    if 0 <= dominant_state < len(labels):
        return labels[dominant_state]
    return f"state_{dominant_state}"


def walk_forward(
    symbol: str,
    data_dir: str = "data",
    model_dir: str = "models",
    train_bars: int = 2000,
    test_bars: int = 500,
    step_bars: int = 500,
    k: int = 3,
    n_restarts: int = 5,
) -> WalkForwardResult:
    """
    Run walk-forward optimization on historical data for a symbol.

    Splits the data into rolling train/test windows, trains a Gaussian HMM
    on each training window, and evaluates on the test window.

    Args:
        symbol: Instrument symbol (e.g., "NQ").
        data_dir: Directory containing CSV data files.
        model_dir: Directory for model output (unused, reserved for future).
        train_bars: Number of bars in each training window.
        test_bars: Number of bars in each test window.
        step_bars: Number of bars to step forward between windows.
        k: Number of HMM states.
        n_restarts: Number of random restarts for HMM training.

    Returns:
        WalkForwardResult with per-window and aggregate statistics.
    """
    result = WalkForwardResult()

    # Load data
    data_path = Path(data_dir) / f"{symbol}.csv"
    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        return result

    data = load_csv_data(str(data_path))
    if data is None:
        logger.error("Failed to load data for %s", symbol)
        return result

    logger.info("Loaded %d bars for %s", len(data), symbol)

    # Compute features
    features = compute_features_batch(
        data["open"].values,
        data["high"].values,
        data["low"].values,
        data["close"].values,
        data["volume"].values,
    )

    # Skip warmup bars
    warmup = 100
    features = features[warmup:]

    # Remove rows with NaN
    valid_mask = ~np.any(np.isnan(features), axis=1)
    features = features[valid_mask]

    logger.info("Using %d valid feature bars (after warmup)", len(features))

    total_bars = len(features)
    min_required = train_bars + test_bars

    if total_bars < min_required:
        logger.error(
            "Insufficient data for walk-forward: %d bars available, need %d "
            "(train=%d + test=%d)",
            total_bars, min_required, train_bars, test_bars,
        )
        return result

    return _walk_forward_on_features(
        features, train_bars, test_bars, step_bars, k, n_restarts,
    )


def _walk_forward_on_features(
    features: np.ndarray,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    k: int,
    n_restarts: int,
) -> WalkForwardResult:
    """
    Core walk-forward logic operating on pre-computed feature arrays.
    Separated from data loading for testability.
    """
    result = WalkForwardResult()
    total_bars = len(features)
    min_required = train_bars + test_bars

    if total_bars < min_required:
        logger.error(
            "Insufficient features for walk-forward: %d bars, need %d",
            total_bars, min_required,
        )
        return result

    # Generate windows
    window_idx = 0
    start = 0
    all_test_lls = []
    all_stabilities = []

    while start + train_bars + test_bars <= total_bars:
        train_start = start
        train_end = start + train_bars
        test_start = train_end
        test_end = min(train_end + test_bars, total_bars)

        train_features = features[train_start:train_end]
        test_features = features[test_start:test_end]

        logger.info(
            "Window %d: train[%d:%d] test[%d:%d]",
            window_idx, train_start, train_end, test_start, test_end,
        )

        # Train HMM on training window
        start_time = time.time()
        model, train_ll = _train_hmm_window(
            train_features, k=k, n_restarts=n_restarts,
        )
        elapsed = time.time() - start_time

        if model is None:
            logger.warning("Window %d: training failed, skipping", window_idx)
            start += step_bars
            window_idx += 1
            continue

        # Score on test data
        try:
            test_ll = model.score(test_features)
        except Exception as e:
            logger.warning("Window %d: test scoring failed: %s", window_idx, e)
            start += step_bars
            window_idx += 1
            continue

        # Predict states on test data for regime stability
        try:
            test_states = model.predict(test_features)
        except Exception as e:
            logger.warning("Window %d: state prediction failed: %s", window_idx, e)
            start += step_bars
            window_idx += 1
            continue

        stability = _compute_regime_stability(test_states)

        # Determine dominant regime (most frequent state in test)
        state_counts = np.bincount(test_states, minlength=k)
        dominant_state = int(np.argmax(state_counts))
        dominant_label = _get_regime_label(dominant_state, k)

        win_result = WindowResult(
            window_idx=window_idx,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_ll=float(train_ll),
            test_ll=float(test_ll),
            regime_stability=stability,
            dominant_regime=dominant_label,
        )

        result.windows.append(win_result)
        all_test_lls.append(test_ll)
        all_stabilities.append(stability)

        logger.info(
            "  Window %d: train_ll=%.2f, test_ll=%.2f, stability=%.3f, "
            "dominant=%s (%.1fs)",
            window_idx, train_ll, test_ll, stability, dominant_label, elapsed,
        )

        start += step_bars
        window_idx += 1

    # Aggregate results
    if all_test_lls:
        result.aggregate_test_ll = float(np.mean(all_test_lls))
        result.stability_score = float(np.mean(all_stabilities))
    result.total_windows = len(result.windows)

    logger.info(
        "Walk-forward complete: %d windows, avg_test_ll=%.2f, stability=%.3f",
        result.total_windows, result.aggregate_test_ll, result.stability_score,
    )

    return result


def print_summary(result: WalkForwardResult, symbol: str) -> None:
    """Print a formatted summary table of walk-forward results."""
    print("\n" + "=" * 80)
    print(f"  WALK-FORWARD OPTIMIZATION REPORT — {symbol}")
    print("=" * 80)

    if not result.windows:
        print("  No windows completed.")
        print("=" * 80)
        return

    # Header
    print(f"  {'Win':>4}  {'Train':>12}  {'Test':>12}  "
          f"{'Train LL':>12}  {'Test LL':>12}  {'Stability':>10}  {'Regime':<12}")
    print("  " + "-" * 76)

    for w in result.windows:
        print(
            f"  {w.window_idx:>4}  "
            f"{w.train_start:>5}-{w.train_end:<5}  "
            f"{w.test_start:>5}-{w.test_end:<5}  "
            f"{w.train_ll:>12.2f}  "
            f"{w.test_ll:>12.2f}  "
            f"{w.regime_stability:>10.3f}  "
            f"{w.dominant_regime:<12}"
        )

    print("  " + "-" * 76)
    print(f"  Total Windows:      {result.total_windows}")
    print(f"  Avg Test LL:        {result.aggregate_test_ll:.2f}")
    print(f"  Stability Score:    {result.stability_score:.3f}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward HMM Optimizer")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol to evaluate")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    parser.add_argument("--model-dir", type=str, default="models", help="Model directory")
    parser.add_argument("--train-bars", type=int, default=2000, help="Training window size")
    parser.add_argument("--test-bars", type=int, default=500, help="Test window size")
    parser.add_argument("--step-bars", type=int, default=500, help="Step size between windows")
    parser.add_argument("--k", type=int, default=3, help="Number of HMM states")
    parser.add_argument("--n-restarts", type=int, default=5, help="Random restarts for HMM")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = walk_forward(
        symbol=args.symbol.upper(),
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        step_bars=args.step_bars,
        k=args.k,
        n_restarts=args.n_restarts,
    )

    print_summary(result, args.symbol.upper())

    if result.total_windows == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
