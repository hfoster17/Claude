"""
Training Pipeline — fits Gaussian HMM models per instrument and exports to JSON.

Usage:
    python train.py --symbol NQ
    python train.py --all
    python train.py --symbol NQ --k 3 --n-restarts 5
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from feature_engine import N_FEATURES, compute_features_batch
from data_pull import load_csv_data, validate_data

logger = logging.getLogger(__name__)

SUPPORTED_SYMBOLS = ["NQ", "ES", "CL", "NG", "GC", "SI", "ZB"]

DEFAULT_CONFIG = {
    "k": 3,
    "n_restarts": 5,
    "max_iter": 200,
    "tol": 1e-4,
    "min_training_bars": 500,
    "variance_floor": 1e-6,
}


def train_hmm(
    features: np.ndarray,
    k: int = 3,
    n_restarts: int = 5,
    max_iter: int = 200,
    tol: float = 1e-4,
) -> Tuple[Optional[Dict], float]:
    """
    Train a Gaussian HMM with diagonal covariance.
    Uses hmmlearn. Multiple random restarts, returns best by log-likelihood.
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
                logger.info("  Restart %d/%d: log-likelihood=%.2f (new best)",
                            restart + 1, n_restarts, score)
            else:
                logger.debug("  Restart %d/%d: log-likelihood=%.2f",
                             restart + 1, n_restarts, score)
        except Exception as e:
            logger.warning("  Restart %d failed: %s", restart + 1, e)

    if best_model is None:
        return None, float("-inf")

    return _extract_params(best_model, features, best_score, n_restarts)


def _extract_params(
    model, features: np.ndarray, log_likelihood: float, n_restarts: int
) -> Tuple[Dict, float]:
    """Extract and sort model parameters into schema-v2 format."""
    k = model.n_components
    n_features = features.shape[1]

    # Get diagonal covariance
    if model.covariance_type == "diag":
        variances = model.covars_.copy()
    elif model.covariance_type == "full":
        variances = np.array([np.diag(model.covars_[i]) for i in range(k)])
    else:
        variances = model.covars_.copy()

    variances = np.maximum(variances, 1e-6)

    # Sort states by total variance ascending (state 0 = lowest vol)
    total_var = variances.sum(axis=1)
    sort_idx = np.argsort(total_var)

    initial_probs = model.startprob_[sort_idx]
    transition_matrix = model.transmat_[sort_idx][:, sort_idx]
    means = model.means_[sort_idx]
    variances = variances[sort_idx]

    initial_probs = initial_probs / initial_probs.sum()

    # Regime labels
    if k == 2:
        labels = ["low_vol", "high_vol"]
    elif k == 3:
        labels = ["low_vol", "trending", "high_vol"]
    else:
        labels = [f"state_{i}" for i in range(k)]

    feature_mean = features.mean(axis=0).tolist()
    feature_std = features.std(axis=0, ddof=1).tolist()
    feature_std = [max(s, 1e-10) for s in feature_std]

    model_dict = {
        "schema_version": 2,
        "k": k,
        "n_features": n_features,
        "initial_probs": initial_probs.tolist(),
        "transition_matrix": transition_matrix.tolist(),
        "means": means.tolist(),
        "variances": variances.tolist(),
        "feature_mean": feature_mean,
        "feature_std": feature_std,
        "regime_labels": labels[:k],
        "metadata": {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_bars": int(features.shape[0]),
            "log_likelihood": float(log_likelihood),
            "converged": bool(model.monitor_.converged),
            "n_iterations": int(model.monitor_.iter),
            "random_restarts": n_restarts,
        },
    }

    return model_dict, log_likelihood


def save_model(model_dict: Dict, symbol: str, output_dir: str) -> str:
    """Save model dict to JSON file."""
    model_dict["symbol"] = symbol
    out_path = Path(output_dir) / f"{symbol}_model.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(model_dict, f, indent=2)

    logger.info("Saved model for %s to %s", symbol, out_path)
    return str(out_path)


def train_symbol(
    symbol: str,
    data_dir: str = "data",
    model_dir: str = "models",
    config: Optional[Dict] = None,
) -> bool:
    """Full training pipeline for one symbol."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    logger.info("=" * 60)
    logger.info("Training model for %s (k=%d, restarts=%d)", symbol, cfg["k"], cfg["n_restarts"])
    logger.info("=" * 60)

    # Load data
    data_path = Path(data_dir) / f"{symbol}.csv"
    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        return False

    data = load_csv_data(str(data_path))
    if data is None:
        logger.error("Failed to load data for %s", symbol)
        return False

    # Validate
    issues = validate_data(data)
    if issues:
        for issue in issues:
            logger.warning("Data issue [%s]: %s", symbol, issue)

    logger.info("Loaded %d bars for %s", len(data), symbol)

    if len(data) < cfg["min_training_bars"]:
        logger.error("Insufficient data for %s: %d bars (need %d)",
                      symbol, len(data), cfg["min_training_bars"])
        return False

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
    logger.info("Training on %d bars (after warmup)", len(features))

    # Remove rows with NaN
    valid_mask = ~np.any(np.isnan(features), axis=1)
    features = features[valid_mask]

    if len(features) < cfg["min_training_bars"]:
        logger.error("Insufficient valid data after cleanup: %d bars", len(features))
        return False

    # Train
    start_time = time.time()
    model_dict, best_ll = train_hmm(
        features,
        k=cfg["k"],
        n_restarts=cfg["n_restarts"],
        max_iter=cfg["max_iter"],
        tol=cfg["tol"],
    )
    elapsed = time.time() - start_time

    if model_dict is None:
        logger.error("HMM training failed for %s", symbol)
        return False

    # Add data range to metadata
    if "timestamp" in data.columns:
        model_dict["metadata"]["data_start"] = str(data["timestamp"].iloc[0])
        model_dict["metadata"]["data_end"] = str(data["timestamp"].iloc[-1])

    # Save
    save_model(model_dict, symbol, model_dir)
    logger.info("Training complete for %s in %.1fs (log-likelihood: %.2f)",
                 symbol, elapsed, best_ll)
    return True


def main():
    parser = argparse.ArgumentParser(description="Train HMM models for futures trading")
    parser.add_argument("--symbol", type=str, help="Symbol to train (e.g., NQ)")
    parser.add_argument("--all", action="store_true", help="Train all symbols")
    parser.add_argument("--k", type=int, default=None, help="Number of HMM states")
    parser.add_argument("--n-restarts", type=int, default=None, help="Random restarts")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    parser.add_argument("--model-dir", type=str, default="models", help="Model output directory")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = dict(DEFAULT_CONFIG)
    if args.k is not None:
        config["k"] = args.k
    if args.n_restarts is not None:
        config["n_restarts"] = args.n_restarts

    symbols: List[str] = []
    if args.all:
        symbols = SUPPORTED_SYMBOLS
    elif args.symbol:
        sym = args.symbol.upper()
        if sym not in SUPPORTED_SYMBOLS:
            logger.error("Unknown symbol: %s. Supported: %s", sym, SUPPORTED_SYMBOLS)
            sys.exit(1)
        symbols = [sym]
    else:
        parser.print_help()
        sys.exit(1)

    results = {}
    for sym in symbols:
        success = train_symbol(sym, args.data_dir, args.model_dir, config)
        results[sym] = "OK" if success else "FAILED"

    print("\n=== Training Results ===")
    for sym, status in results.items():
        print(f"  {sym}: {status}")

    if any(s == "FAILED" for s in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
