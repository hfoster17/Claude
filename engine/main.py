"""
Multi-Regime Trading Engine — main entry point.

Usage:
    python main.py --serve                  # Start inference server
    python main.py --serve --port 5555      # Custom port
    python main.py --train --symbol NQ      # Train single symbol
    python main.py --train --all            # Train all symbols
    python main.py --status                 # Check engine status
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from model_manager import ModelManager
from server import InferenceServer, status_writer_loop

logger = logging.getLogger("engine")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555
DEFAULT_MODEL_DIR = "models"
DEFAULT_DATA_DIR = "data"
DEFAULT_LOG_DIR = "logs"
DEFAULT_STATUS_FILE = "engine_status.json"


def setup_logging(log_dir: str = DEFAULT_LOG_DIR, level: str = "INFO") -> None:
    """Configure structured rotating logs."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root_logger.addHandler(console)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "engine.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root_logger.addHandler(file_handler)


async def run_server(args) -> None:
    """Run the inference server."""
    model_manager = ModelManager(args.model_dir)
    count = model_manager.load_all()
    logger.info("Loaded %d models at startup", count)

    if count == 0:
        logger.warning("No models loaded — server will respond with MODEL_NOT_FOUND until models are available")

    # Start model hot-reload watcher
    def on_model_reload(symbol: str):
        logger.info("Model reloaded callback: %s", symbol)

    model_manager.start_watcher(poll_interval=5.0, on_reload=on_model_reload)

    server = InferenceServer(model_manager, args.host, args.port)

    # Set up graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received")
        model_manager.stop_watcher()
        loop.create_task(server.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Start status file writer
    status_task = asyncio.create_task(
        status_writer_loop(server, args.status_file, interval=5.0)
    )

    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        status_task.cancel()
        model_manager.stop_watcher()
        logger.info("Engine shutdown complete")


def run_train(args) -> None:
    """Run training pipeline."""
    from train import train_symbol, SUPPORTED_SYMBOLS

    if args.all:
        symbols = SUPPORTED_SYMBOLS
    elif args.symbol:
        symbols = [args.symbol.upper()]
    else:
        logger.error("Specify --symbol or --all for training")
        sys.exit(1)

    results = {}
    for sym in symbols:
        config = {"k": args.k} if args.k else {}
        success = train_symbol(sym, args.data_dir, args.model_dir, config)
        results[sym] = "OK" if success else "FAILED"

    print("\n=== Training Results ===")
    for sym, status in results.items():
        print(f"  {sym}: {status}")

    if any(s == "FAILED" for s in results.values()):
        sys.exit(1)


def show_status(args) -> None:
    """Show engine status from status file."""
    import json

    status_path = args.status_file
    if not os.path.exists(status_path):
        print(f"Status file not found: {status_path}")
        print("Is the engine running?")
        sys.exit(1)

    with open(status_path) as f:
        status = json.load(f)

    print("=== Engine Status ===")
    print(f"  Uptime: {status.get('uptime_s', 0):.0f}s")
    print(f"  Total Requests: {status.get('total_requests', 0)}")
    print(f"  Total Errors: {status.get('total_errors', 0)}")
    print(f"  Avg Latency: {status.get('avg_latency_ms', 0):.3f}ms")
    print(f"  Models Loaded: {status.get('models_loaded', [])}")

    per_sym = status.get("per_symbol_requests", {})
    if per_sym:
        print("  Per-Symbol Requests:")
        for sym, cnt in per_sym.items():
            print(f"    {sym}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="Multi-Regime Trading Engine")
    parser.add_argument("--serve", action="store_true", help="Start inference server")
    parser.add_argument("--train", action="store_true", help="Run training pipeline")
    parser.add_argument("--status", action="store_true", help="Show engine status")

    # Server options
    parser.add_argument("--host", type=str, default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model-dir", type=str, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--status-file", type=str, default=DEFAULT_STATUS_FILE)

    # Training options
    parser.add_argument("--symbol", type=str, help="Symbol to train")
    parser.add_argument("--all", action="store_true", help="Train all symbols")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--k", type=int, default=None, help="HMM states override")

    # General
    parser.add_argument("--log-dir", type=str, default=DEFAULT_LOG_DIR)
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    setup_logging(args.log_dir, args.log_level)

    if args.serve:
        logger.info("Starting Multi-Regime Trading Engine (server mode)")
        asyncio.run(run_server(args))
    elif args.train:
        logger.info("Starting Multi-Regime Trading Engine (training mode)")
        run_train(args)
    elif args.status:
        show_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
