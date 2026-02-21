"""
Monte Carlo Stress Testing — simulates trade P&L under randomized conditions.

Runs N simulations with shuffled trade ordering, optional slippage noise,
and optional trade skip rate. Reports P&L percentiles, drawdown statistics,
and pass/fail rate against configurable thresholds.

Usage:
    python monte_carlo.py --trades-file trades.csv --n-sims 10000
    python monte_carlo.py --trades-file trades.csv --profit-target 5000 --max-dd 3000
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Aggregated results from Monte Carlo stress test simulations."""

    # P&L percentiles
    median_pnl: float
    mean_pnl: float
    pct_5_pnl: float
    pct_95_pnl: float

    # Drawdown percentiles
    median_max_dd: float
    mean_max_dd: float
    pct_5_dd: float
    pct_95_dd: float

    # Pass rate: fraction of sims meeting both profit target and max drawdown
    pass_rate: float

    # Raw simulation outputs
    all_final_pnls: List[float] = field(default_factory=list)
    all_max_drawdowns: List[float] = field(default_factory=list)


def _compute_max_drawdown(cumulative_pnl: np.ndarray) -> float:
    """
    Compute maximum peak-to-trough drawdown from a cumulative P&L curve.
    Returns a non-negative value (0 means no drawdown).
    """
    if len(cumulative_pnl) == 0:
        return 0.0

    peak = cumulative_pnl[0]
    max_dd = 0.0

    for val in cumulative_pnl:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    return float(max_dd)


def _compute_max_consecutive_losses(trades: np.ndarray) -> int:
    """Count the longest streak of consecutive losing trades (P&L < 0)."""
    if len(trades) == 0:
        return 0

    max_streak = 0
    current_streak = 0

    for pnl in trades:
        if pnl < 0:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0

    return max_streak


def _run_single_simulation(
    trades: np.ndarray,
    rng: np.random.RandomState,
    slippage_per_trade: float,
    skip_rate: float,
) -> Tuple[float, float, int]:
    """
    Run one Monte Carlo simulation.

    Returns (final_pnl, max_drawdown, max_consecutive_losses).
    """
    # Shuffle trade order
    shuffled = trades.copy()
    rng.shuffle(shuffled)

    # Apply skip rate: randomly drop trades
    if skip_rate > 0.0:
        mask = rng.random(len(shuffled)) >= skip_rate
        shuffled = shuffled[mask]

    if len(shuffled) == 0:
        return 0.0, 0.0, 0

    # Apply slippage noise
    if slippage_per_trade > 0.0:
        noise = rng.normal(0.0, slippage_per_trade, size=len(shuffled))
        shuffled = shuffled + noise

    # Compute cumulative P&L
    cumulative_pnl = np.cumsum(shuffled)

    final_pnl = float(cumulative_pnl[-1])
    max_dd = _compute_max_drawdown(cumulative_pnl)
    max_consec = _compute_max_consecutive_losses(shuffled)

    return final_pnl, max_dd, max_consec


def run_monte_carlo(
    trades: List[float],
    n_simulations: int = 10000,
    profit_target: float = 3000.0,
    max_allowed_drawdown: float = 2500.0,
    slippage_per_trade: float = 0.0,
    skip_rate: float = 0.0,
    seed: int = 42,
) -> MonteCarloResult:
    """
    Run Monte Carlo stress test on a list of trade P&L results.

    Args:
        trades: List of individual trade P&L values.
        n_simulations: Number of randomized simulations to run.
        profit_target: Minimum final P&L to count as a passing simulation.
        max_allowed_drawdown: Maximum drawdown allowed for a passing simulation.
        slippage_per_trade: Std dev of gaussian noise added per trade (0 = none).
        skip_rate: Probability of dropping each trade per simulation (0 = none).
        seed: Random seed for reproducibility.

    Returns:
        MonteCarloResult with aggregated statistics.
    """
    if len(trades) == 0:
        logger.warning("Empty trades list provided — returning zero result")
        return MonteCarloResult(
            median_pnl=0.0,
            mean_pnl=0.0,
            pct_5_pnl=0.0,
            pct_95_pnl=0.0,
            median_max_dd=0.0,
            mean_max_dd=0.0,
            pct_5_dd=0.0,
            pct_95_dd=0.0,
            pass_rate=0.0,
            all_final_pnls=[],
            all_max_drawdowns=[],
        )

    trades_arr = np.array(trades, dtype=np.float64)
    rng = np.random.RandomState(seed)

    all_final_pnls = []
    all_max_drawdowns = []
    pass_count = 0

    logger.info(
        "Running %d Monte Carlo simulations on %d trades "
        "(slippage=%.2f, skip_rate=%.2f)",
        n_simulations, len(trades_arr), slippage_per_trade, skip_rate,
    )

    for i in range(n_simulations):
        final_pnl, max_dd, _ = _run_single_simulation(
            trades_arr, rng, slippage_per_trade, skip_rate,
        )

        all_final_pnls.append(final_pnl)
        all_max_drawdowns.append(max_dd)

        if final_pnl > profit_target and max_dd < max_allowed_drawdown:
            pass_count += 1

        if (i + 1) % 5000 == 0:
            logger.debug("  Completed %d/%d simulations", i + 1, n_simulations)

    pnls = np.array(all_final_pnls)
    dds = np.array(all_max_drawdowns)

    result = MonteCarloResult(
        median_pnl=float(np.median(pnls)),
        mean_pnl=float(np.mean(pnls)),
        pct_5_pnl=float(np.percentile(pnls, 5)),
        pct_95_pnl=float(np.percentile(pnls, 95)),
        median_max_dd=float(np.median(dds)),
        mean_max_dd=float(np.mean(dds)),
        pct_5_dd=float(np.percentile(dds, 5)),
        pct_95_dd=float(np.percentile(dds, 95)),
        pass_rate=pass_count / n_simulations,
        all_final_pnls=all_final_pnls,
        all_max_drawdowns=all_max_drawdowns,
    )

    logger.info(
        "Monte Carlo complete: median_pnl=%.2f, median_dd=%.2f, pass_rate=%.2f%%",
        result.median_pnl, result.median_max_dd, result.pass_rate * 100,
    )

    return result


def load_trades_from_csv(filepath: str) -> List[float]:
    """Load trade P&L values from a CSV file (one value per line)."""
    path = Path(filepath)
    if not path.exists():
        logger.error("Trades file not found: %s", filepath)
        return []

    trades = []
    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                trades.append(float(line))
            except ValueError:
                logger.warning("Skipping non-numeric line %d: %s", line_num, line)

    logger.info("Loaded %d trades from %s", len(trades), filepath)
    return trades


def print_report(result: MonteCarloResult, n_sims: int) -> None:
    """Print a formatted summary report of Monte Carlo results."""
    print("\n" + "=" * 60)
    print("  MONTE CARLO STRESS TEST REPORT")
    print("=" * 60)
    print(f"  Simulations:     {n_sims:,}")
    print(f"  Pass Rate:       {result.pass_rate * 100:.1f}%")
    print()
    print("  --- P&L Statistics ---")
    print(f"  Mean P&L:        ${result.mean_pnl:>12,.2f}")
    print(f"  Median P&L:      ${result.median_pnl:>12,.2f}")
    print(f"  5th Percentile:  ${result.pct_5_pnl:>12,.2f}")
    print(f"  95th Percentile: ${result.pct_95_pnl:>12,.2f}")
    print()
    print("  --- Drawdown Statistics ---")
    print(f"  Mean Max DD:     ${result.mean_max_dd:>12,.2f}")
    print(f"  Median Max DD:   ${result.median_max_dd:>12,.2f}")
    print(f"  5th Percentile:  ${result.pct_5_dd:>12,.2f}")
    print(f"  95th Percentile: ${result.pct_95_dd:>12,.2f}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo Stress Testing for trade P&L")
    parser.add_argument("--trades-file", type=str, required=True,
                        help="CSV file with one P&L value per line")
    parser.add_argument("--n-sims", type=int, default=10000,
                        help="Number of simulations (default: 10000)")
    parser.add_argument("--profit-target", type=float, default=3000.0,
                        help="Minimum final P&L for passing (default: 3000)")
    parser.add_argument("--max-dd", type=float, default=2500.0,
                        help="Maximum allowed drawdown for passing (default: 2500)")
    parser.add_argument("--slippage", type=float, default=0.0,
                        help="Gaussian slippage std per trade (default: 0)")
    parser.add_argument("--skip-rate", type=float, default=0.0,
                        help="Probability of dropping each trade (default: 0)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    trades = load_trades_from_csv(args.trades_file)
    if not trades:
        logger.error("No trades loaded — exiting")
        sys.exit(1)

    result = run_monte_carlo(
        trades=trades,
        n_simulations=args.n_sims,
        profit_target=args.profit_target,
        max_allowed_drawdown=args.max_dd,
        slippage_per_trade=args.slippage,
        skip_rate=args.skip_rate,
        seed=args.seed,
    )

    print_report(result, args.n_sims)


if __name__ == "__main__":
    main()
