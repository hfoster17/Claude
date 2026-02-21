"""
Scheduler — nightly retrain + drift-triggered retrain.

Usage:
    python scheduler.py                     # Run scheduler
    python scheduler.py --retrain-time 02:00
"""

import argparse
import logging
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import schedule

from data_pull import load_csv_data, validate_data, NT8ExportWatcher
from drift import DriftManager
from train import train_symbol, SUPPORTED_SYMBOLS

logger = logging.getLogger(__name__)

DEFAULT_RETRAIN_TIME = "02:00"


class RetrainScheduler:
    """
    Manages scheduled and drift-triggered retraining.
    """

    def __init__(
        self,
        data_dir: str = "data",
        model_dir: str = "models",
        retrain_time: str = DEFAULT_RETRAIN_TIME,
        symbols: Optional[List[str]] = None,
        drift_manager: Optional[DriftManager] = None,
        drift_check_interval_min: int = 30,
    ):
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.retrain_time = retrain_time
        self.symbols = symbols or SUPPORTED_SYMBOLS
        self.drift_manager = drift_manager
        self.drift_check_interval_min = drift_check_interval_min
        self._running = False
        self._last_retrain: Dict[str, str] = {}

    def retrain_all(self) -> Dict[str, bool]:
        """Retrain models for all configured symbols."""
        logger.info("=" * 60)
        logger.info("Starting scheduled retrain for all symbols")
        logger.info("=" * 60)

        results = {}
        for sym in self.symbols:
            try:
                success = train_symbol(sym, self.data_dir, self.model_dir)
                results[sym] = success
                if success:
                    self._last_retrain[sym] = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.error("Retrain failed for %s: %s", sym, e)
                results[sym] = False

        successes = sum(1 for v in results.values() if v)
        logger.info("Retrain complete: %d/%d succeeded", successes, len(results))
        return results

    def retrain_symbol(self, symbol: str) -> bool:
        """Retrain a single symbol."""
        logger.info("Retraining %s...", symbol)
        try:
            success = train_symbol(symbol, self.data_dir, self.model_dir)
            if success:
                self._last_retrain[symbol] = datetime.now(timezone.utc).isoformat()
            return success
        except Exception as e:
            logger.error("Retrain failed for %s: %s", symbol, e)
            return False

    def check_drift_retrain(self) -> None:
        """Check drift metrics and trigger retrain if needed."""
        if self.drift_manager is None:
            return

        results = self.drift_manager.check_all_retrain()
        for sym, (should_retrain, reasons) in results.items():
            if should_retrain:
                logger.warning("Drift detected for %s: %s", sym, "; ".join(reasons))
                self.retrain_symbol(sym)

    def start(self) -> None:
        """Start the scheduler (blocking)."""
        self._running = True

        # Schedule nightly retrain
        schedule.every().day.at(self.retrain_time).do(self.retrain_all)
        logger.info("Scheduled nightly retrain at %s", self.retrain_time)

        # Schedule drift checks
        if self.drift_manager is not None:
            schedule.every(self.drift_check_interval_min).minutes.do(self.check_drift_retrain)
            logger.info("Scheduled drift checks every %d minutes", self.drift_check_interval_min)

        logger.info("Scheduler started. Press Ctrl+C to stop.")

        while self._running:
            schedule.run_pending()
            time.sleep(10)

    def start_background(self) -> threading.Thread:
        """Start the scheduler in a background thread."""
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._running = False
        logger.info("Scheduler stopped")

    def get_status(self) -> Dict:
        """Return scheduler status."""
        return {
            "running": self._running,
            "retrain_time": self.retrain_time,
            "symbols": self.symbols,
            "last_retrain": dict(self._last_retrain),
            "next_run": str(schedule.next_run()) if schedule.jobs else "none",
        }


def main():
    parser = argparse.ArgumentParser(description="Retrain scheduler")
    parser.add_argument("--retrain-time", type=str, default=DEFAULT_RETRAIN_TIME,
                        help="Daily retrain time (HH:MM)")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--model-dir", type=str, default="models")
    parser.add_argument("--drift-check-interval", type=int, default=30,
                        help="Drift check interval in minutes")
    parser.add_argument("--symbols", type=str, nargs="*", default=None,
                        help="Symbols to retrain (default: all)")
    parser.add_argument("--once", action="store_true",
                        help="Run retrain once and exit")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    symbols = [s.upper() for s in args.symbols] if args.symbols else SUPPORTED_SYMBOLS

    sched = RetrainScheduler(
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        retrain_time=args.retrain_time,
        symbols=symbols,
        drift_check_interval_min=args.drift_check_interval,
    )

    if args.once:
        sched.retrain_all()
        return

    try:
        sched.start()
    except KeyboardInterrupt:
        sched.stop()


if __name__ == "__main__":
    main()
