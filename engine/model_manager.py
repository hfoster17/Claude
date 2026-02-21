"""
Model Manager — loads, validates, and hot-reloads HMM models from disk.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from hmm_inference import HMMModel

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "schema_version", "symbol", "k", "n_features",
    "initial_probs", "transition_matrix", "means", "variances",
    "feature_mean", "feature_std", "regime_labels", "metadata",
]

SUPPORTED_SYMBOLS = {"NQ", "ES", "CL", "NG", "GC", "SI", "ZB", "UB"}
CURRENT_SCHEMA_VERSION = 2


def validate_model_dict(d: Dict) -> Optional[str]:
    """Validate a model dictionary. Returns error string or None if valid."""
    for field in REQUIRED_FIELDS:
        if field not in d:
            return f"Missing required field: {field}"

    if d["schema_version"] != CURRENT_SCHEMA_VERSION:
        return f"Unsupported schema version: {d['schema_version']} (expected {CURRENT_SCHEMA_VERSION})"

    if d["symbol"] not in SUPPORTED_SYMBOLS:
        return f"Unknown symbol: {d['symbol']}"

    k = d["k"]
    nf = d["n_features"]

    if len(d["initial_probs"]) != k:
        return f"initial_probs length {len(d['initial_probs'])} != k={k}"
    if len(d["transition_matrix"]) != k:
        return f"transition_matrix rows {len(d['transition_matrix'])} != k={k}"
    for i, row in enumerate(d["transition_matrix"]):
        if len(row) != k:
            return f"transition_matrix row {i} length {len(row)} != k={k}"
    if len(d["means"]) != k:
        return f"means rows {len(d['means'])} != k={k}"
    for i, row in enumerate(d["means"]):
        if len(row) != nf:
            return f"means row {i} length {len(row)} != n_features={nf}"
    if len(d["variances"]) != k:
        return f"variances rows {len(d['variances'])} != k={k}"
    if len(d["feature_mean"]) != nf:
        return f"feature_mean length {len(d['feature_mean'])} != n_features={nf}"
    if len(d["feature_std"]) != nf:
        return f"feature_std length {len(d['feature_std'])} != n_features={nf}"
    if len(d["regime_labels"]) != k:
        return f"regime_labels length {len(d['regime_labels'])} != k={k}"

    return None


def load_model_file(path: str) -> Optional[HMMModel]:
    """Load and validate a single model JSON file."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        error = validate_model_dict(data)
        if error:
            logger.error("Model validation failed for %s: %s", path, error)
            return None
        model = HMMModel(data)
        logger.info("Loaded model for %s from %s (trained %s)",
                     model.symbol, path, model.metadata.get("trained_at", "unknown"))
        return model
    except json.JSONDecodeError as e:
        logger.error("JSON parse error in %s: %s", path, e)
        return None
    except Exception as e:
        logger.error("Failed to load model %s: %s", path, e)
        return None


class ModelManager:
    """
    Manages HMM models for all symbols.
    Supports hot-reload by watching the model directory.
    """

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)
        self._models: Dict[str, HMMModel] = {}
        self._file_mtimes: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._watcher_thread: Optional[threading.Thread] = None
        self._running = False
        self._on_reload: Optional[Callable[[str], None]] = None

    @property
    def loaded_symbols(self) -> list:
        with self._lock:
            return list(self._models.keys())

    def get_model(self, symbol: str) -> Optional[HMMModel]:
        with self._lock:
            return self._models.get(symbol)

    def load_all(self) -> int:
        """Load all model files from the model directory. Returns count loaded."""
        if not self.model_dir.exists():
            logger.warning("Model directory does not exist: %s", self.model_dir)
            return 0

        count = 0
        for path in self.model_dir.glob("*_model.json"):
            model = load_model_file(str(path))
            if model:
                with self._lock:
                    self._models[model.symbol] = model
                    self._file_mtimes[str(path)] = os.path.getmtime(path)
                count += 1

        logger.info("Loaded %d models from %s", count, self.model_dir)
        return count

    def reload_symbol(self, symbol: str) -> bool:
        """Reload a specific symbol's model from disk."""
        path = self.model_dir / f"{symbol}_model.json"
        if not path.exists():
            logger.warning("Model file not found: %s", path)
            return False

        model = load_model_file(str(path))
        if model:
            with self._lock:
                self._models[model.symbol] = model
                self._file_mtimes[str(path)] = os.path.getmtime(path)
            if self._on_reload:
                self._on_reload(symbol)
            return True
        return False

    def start_watcher(self, poll_interval: float = 5.0, on_reload: Optional[Callable] = None) -> None:
        """Start background thread that polls for model file changes."""
        self._on_reload = on_reload
        self._running = True
        self._watcher_thread = threading.Thread(
            target=self._watch_loop, args=(poll_interval,), daemon=True
        )
        self._watcher_thread.start()
        logger.info("Model watcher started (poll interval: %.1fs)", poll_interval)

    def stop_watcher(self) -> None:
        self._running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=10)
            logger.info("Model watcher stopped")

    def _watch_loop(self, poll_interval: float) -> None:
        while self._running:
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error("Watcher error: %s", e)
            time.sleep(poll_interval)

    def _check_for_changes(self) -> None:
        if not self.model_dir.exists():
            return

        for path in self.model_dir.glob("*_model.json"):
            path_str = str(path)
            current_mtime = os.path.getmtime(path)

            with self._lock:
                prev_mtime = self._file_mtimes.get(path_str, 0)

            if current_mtime > prev_mtime:
                logger.info("Detected change in %s, reloading...", path.name)
                model = load_model_file(path_str)
                if model:
                    with self._lock:
                        self._models[model.symbol] = model
                        self._file_mtimes[path_str] = current_mtime
                    logger.info("Hot-reloaded model for %s", model.symbol)
                    if self._on_reload:
                        self._on_reload(model.symbol)

    def get_status(self) -> Dict:
        """Return status dict for all loaded models."""
        with self._lock:
            return {
                symbol: {
                    "version": m.schema_version,
                    "k": m.k,
                    "trained_at": m.metadata.get("trained_at", "unknown"),
                    "training_bars": m.metadata.get("training_bars", 0),
                }
                for symbol, m in self._models.items()
            }
