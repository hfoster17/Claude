"""
Data Pull — historical data acquisition, validation, and ingestion.

Supports:
  - CSV file ingestion (standard OHLCV format)
  - NT8 export folder watcher
  - Broker/public API stubs (abstract adapter)

Usage:
    python data_pull.py --symbol NQ --source csv --file data/NQ.csv
    python data_pull.py --watch-dir /path/to/nt8/exports
"""

import argparse
import csv
import logging
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def load_csv_data(filepath: str) -> Optional[pd.DataFrame]:
    """
    Load OHLCV data from CSV. Expected columns:
    timestamp, open, high, low, close, volume

    Also accepts: Date/Time, Open, High, Low, Close, Volume (NT8 export format)
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        logger.error("Failed to read CSV %s: %s", filepath, e)
        return None

    # Normalize column names
    col_map = {}
    for col in df.columns:
        lower = col.strip().lower().replace(" ", "_").replace("/", "_")
        if lower in ("date", "datetime", "date_time", "time", "timestamp"):
            col_map[col] = "timestamp"
        elif lower == "open":
            col_map[col] = "open"
        elif lower == "high":
            col_map[col] = "high"
        elif lower == "low":
            col_map[col] = "low"
        elif lower in ("close", "last"):
            col_map[col] = "close"
        elif lower in ("volume", "vol"):
            col_map[col] = "volume"

    df = df.rename(columns=col_map)

    # Verify required columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        logger.error("Missing columns in %s: %s. Found: %s", filepath, missing, list(df.columns))
        return None

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    # Convert numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with NaN in critical columns
    before = len(df)
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    after = len(df)
    if before != after:
        logger.warning("Dropped %d rows with NaN values from %s", before - after, filepath)

    # Fill missing volume with 0
    df["volume"] = df["volume"].fillna(0)

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info("Loaded %d bars from %s", len(df), filepath)
    return df


def validate_data(df: pd.DataFrame) -> List[str]:
    """
    Validate OHLCV data for common issues.
    Returns list of warning strings (empty if clean).
    """
    issues = []

    if len(df) < 200:
        issues.append(f"Very few bars: {len(df)} (recommend > 10000 for training)")

    # Check for duplicates
    dupes = df["timestamp"].duplicated().sum()
    if dupes > 0:
        issues.append(f"Found {dupes} duplicate timestamps")

    # Check OHLC consistency
    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl > 0:
        issues.append(f"Found {bad_hl} bars where high < low")

    bad_oh = (df["open"] > df["high"]).sum()
    bad_ol = (df["open"] < df["low"]).sum()
    if bad_oh > 0:
        issues.append(f"Found {bad_oh} bars where open > high")
    if bad_ol > 0:
        issues.append(f"Found {bad_ol} bars where open < low")

    # Check for gaps
    if len(df) > 1 and "timestamp" in df.columns:
        diffs = df["timestamp"].diff().dropna()
        median_diff = diffs.median()
        if median_diff.total_seconds() > 0:
            large_gaps = diffs[diffs > median_diff * 3]
            if len(large_gaps) > 0:
                issues.append(f"Found {len(large_gaps)} time gaps > 3x median interval")

    # Check for price outliers (> 10 sigma moves)
    if len(df) > 20:
        log_rets = np.log(df["close"] / df["close"].shift(1)).dropna()
        if len(log_rets) > 0:
            mean_ret = log_rets.mean()
            std_ret = log_rets.std()
            if std_ret > 0:
                outliers = (np.abs(log_rets - mean_ret) > 10 * std_ret).sum()
                if outliers > 0:
                    issues.append(f"Found {outliers} price outliers (> 10 sigma)")

    # Check for zero/negative prices
    zero_prices = (df["close"] <= 0).sum()
    if zero_prices > 0:
        issues.append(f"Found {zero_prices} bars with zero/negative close price")

    return issues


class DataAdapter(ABC):
    """Abstract base class for data source adapters."""

    @abstractmethod
    def fetch(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        pass

    @abstractmethod
    def name(self) -> str:
        pass


class CSVAdapter(DataAdapter):
    """Load data from local CSV files."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def fetch(self, symbol: str, start_date: str = "", end_date: str = "") -> Optional[pd.DataFrame]:
        path = self.data_dir / f"{symbol}.csv"
        if not path.exists():
            logger.error("CSV not found: %s", path)
            return None
        return load_csv_data(str(path))

    def name(self) -> str:
        return "csv"


class BrokerAPIAdapter(DataAdapter):
    """
    Stub adapter for broker/public API integration.
    Override fetch() with your broker's API client.
    """

    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    def fetch(self, symbol: str, start_date: str = "", end_date: str = "") -> Optional[pd.DataFrame]:
        logger.warning(
            "BrokerAPIAdapter.fetch() is a stub. "
            "Implement your broker's API here for symbol=%s", symbol
        )
        return None

    def name(self) -> str:
        return "broker_api"


class NT8ExportWatcher:
    """
    Watch a directory for NT8 CSV exports and ingest them.
    NT8 can export bar data via Tools > Export > Bars.
    """

    def __init__(self, watch_dir: str, data_dir: str = "data", poll_interval: float = 10.0):
        self.watch_dir = Path(watch_dir)
        self.data_dir = Path(data_dir)
        self.poll_interval = poll_interval
        self._processed: set = set()
        self._running = False

    def start(self) -> None:
        """Start watching for new exports (blocking)."""
        self._running = True
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Watching %s for NT8 exports...", self.watch_dir)

        while self._running:
            try:
                self._scan()
            except Exception as e:
                logger.error("Watcher scan error: %s", e)
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False

    def _scan(self) -> None:
        if not self.watch_dir.exists():
            return

        for path in self.watch_dir.glob("*.csv"):
            if path.name in self._processed:
                continue

            # Try to detect symbol from filename
            symbol = self._detect_symbol(path.name)
            if symbol is None:
                logger.warning("Cannot determine symbol for %s, skipping", path.name)
                self._processed.add(path.name)
                continue

            logger.info("Found new export: %s → %s", path.name, symbol)

            # Load and validate
            df = load_csv_data(str(path))
            if df is not None:
                issues = validate_data(df)
                for issue in issues:
                    logger.warning("  %s: %s", symbol, issue)

                # Save to data directory
                dest = self.data_dir / f"{symbol}.csv"
                shutil.copy2(str(path), str(dest))
                logger.info("  Ingested %d bars for %s → %s", len(df), symbol, dest)

            self._processed.add(path.name)

    @staticmethod
    def _detect_symbol(filename: str) -> Optional[str]:
        """Try to extract instrument symbol from filename."""
        upper = filename.upper()
        for sym in ["NQ", "ES", "CL", "NG", "GC", "SI", "ZB"]:
            if sym in upper:
                return sym
        return None


def main():
    parser = argparse.ArgumentParser(description="Historical data pull and validation")
    parser.add_argument("--symbol", type=str, help="Symbol to process")
    parser.add_argument("--source", type=str, choices=["csv", "broker"], default="csv")
    parser.add_argument("--file", type=str, help="Specific CSV file to load")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--watch-dir", type=str, help="NT8 export directory to watch")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't ingest")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.watch_dir:
        watcher = NT8ExportWatcher(args.watch_dir, args.data_dir)
        try:
            watcher.start()
        except KeyboardInterrupt:
            watcher.stop()
            logger.info("Watcher stopped")
        return

    if args.file:
        df = load_csv_data(args.file)
    elif args.symbol:
        adapter = CSVAdapter(args.data_dir)
        df = adapter.fetch(args.symbol.upper())
    else:
        parser.print_help()
        sys.exit(1)

    if df is None:
        sys.exit(1)

    issues = validate_data(df)
    if issues:
        logger.warning("Validation issues found:")
        for issue in issues:
            logger.warning("  - %s", issue)
    else:
        logger.info("Data validation passed — no issues found")

    if args.validate_only:
        return

    logger.info("Data shape: %s", df.shape)
    logger.info("Date range: %s to %s",
                df["timestamp"].iloc[0] if "timestamp" in df.columns else "?",
                df["timestamp"].iloc[-1] if "timestamp" in df.columns else "?")


if __name__ == "__main__":
    main()
