"""Tests for monte_carlo.py — Monte Carlo stress testing."""

import numpy as np
import pytest

from monte_carlo import (
    MonteCarloResult,
    run_monte_carlo,
    _compute_max_drawdown,
    _compute_max_consecutive_losses,
)


@pytest.fixture
def winning_trades():
    """100 trades that are all profitable."""
    return [50.0] * 100


@pytest.fixture
def losing_trades():
    """100 trades that are all losses."""
    return [-50.0] * 100


@pytest.fixture
def mixed_trades():
    """100 trades with a mix of wins and losses, net positive."""
    np.random.seed(99)
    return list(np.random.normal(10.0, 30.0, 100))


class TestBasicRun:
    def test_basic_run(self, mixed_trades):
        """Verify result fields exist and are populated correctly."""
        result = run_monte_carlo(
            trades=mixed_trades,
            n_simulations=500,
            profit_target=500.0,
            max_allowed_drawdown=2000.0,
            seed=42,
        )

        assert isinstance(result, MonteCarloResult)
        assert isinstance(result.median_pnl, float)
        assert isinstance(result.mean_pnl, float)
        assert isinstance(result.pct_5_pnl, float)
        assert isinstance(result.pct_95_pnl, float)
        assert isinstance(result.median_max_dd, float)
        assert isinstance(result.mean_max_dd, float)
        assert isinstance(result.pct_5_dd, float)
        assert isinstance(result.pct_95_dd, float)
        assert isinstance(result.pass_rate, float)
        assert len(result.all_final_pnls) == 500
        assert len(result.all_max_drawdowns) == 500

        # Percentiles should be ordered
        assert result.pct_5_pnl <= result.median_pnl <= result.pct_95_pnl
        assert result.pct_5_dd <= result.median_max_dd <= result.pct_95_dd

    def test_result_pnl_count(self, mixed_trades):
        """Verify correct number of simulations are recorded."""
        n_sims = 200
        result = run_monte_carlo(
            trades=mixed_trades, n_simulations=n_sims, seed=42,
        )
        assert len(result.all_final_pnls) == n_sims
        assert len(result.all_max_drawdowns) == n_sims


class TestAllWinningTrades:
    def test_all_winning_trades(self, winning_trades):
        """All winning trades should yield high pass rate."""
        result = run_monte_carlo(
            trades=winning_trades,
            n_simulations=500,
            profit_target=3000.0,
            max_allowed_drawdown=5000.0,
            seed=42,
        )

        # Sum is 5000, all positive, no drawdown — should always pass
        assert result.pass_rate > 0.99
        assert result.median_pnl == pytest.approx(5000.0)
        assert result.mean_pnl == pytest.approx(5000.0)

        # No drawdowns for all-winning trades
        assert result.median_max_dd == pytest.approx(0.0)


class TestAllLosingTrades:
    def test_all_losing_trades(self, losing_trades):
        """All losing trades should yield 0% pass rate."""
        result = run_monte_carlo(
            trades=losing_trades,
            n_simulations=500,
            profit_target=0.0,
            max_allowed_drawdown=100.0,
            seed=42,
        )

        # Final P&L is -5000, which is not > 0 — pass rate must be 0
        assert result.pass_rate == 0.0
        assert result.median_pnl < 0
        assert result.mean_pnl < 0


class TestDeterministicWithSeed:
    def test_deterministic_with_seed(self, mixed_trades):
        """Same seed should produce identical results."""
        result1 = run_monte_carlo(
            trades=mixed_trades, n_simulations=1000, seed=123,
        )
        result2 = run_monte_carlo(
            trades=mixed_trades, n_simulations=1000, seed=123,
        )

        assert result1.median_pnl == result2.median_pnl
        assert result1.mean_pnl == result2.mean_pnl
        assert result1.pct_5_pnl == result2.pct_5_pnl
        assert result1.pct_95_pnl == result2.pct_95_pnl
        assert result1.pass_rate == result2.pass_rate
        assert result1.all_final_pnls == result2.all_final_pnls
        assert result1.all_max_drawdowns == result2.all_max_drawdowns

    def test_different_seed_different_results(self, mixed_trades):
        """Different seeds should produce different results."""
        result1 = run_monte_carlo(
            trades=mixed_trades, n_simulations=500, seed=1,
        )
        result2 = run_monte_carlo(
            trades=mixed_trades, n_simulations=500, seed=999,
        )

        # Extremely unlikely to be identical with different seeds
        assert result1.all_final_pnls != result2.all_final_pnls


class TestSlippage:
    def test_slippage_reduces_pnl(self):
        """Adding slippage should increase P&L variance and affect drawdowns."""
        # Use trades with small positive values where slippage noise can flip signs
        small_win_trades = [5.0] * 100

        result_no_slip = run_monte_carlo(
            trades=small_win_trades,
            n_simulations=2000,
            slippage_per_trade=0.0,
            seed=42,
        )
        result_with_slip = run_monte_carlo(
            trades=small_win_trades,
            n_simulations=2000,
            slippage_per_trade=20.0,
            seed=42,
        )

        # Slippage with std=20 on trades of +5 will frequently flip trades negative,
        # creating drawdowns where there were none before.
        assert result_with_slip.mean_max_dd > result_no_slip.mean_max_dd

        # Slippage increases P&L spread (5th/95th percentile range widens)
        spread_no_slip = result_no_slip.pct_95_pnl - result_no_slip.pct_5_pnl
        spread_with_slip = result_with_slip.pct_95_pnl - result_with_slip.pct_5_pnl
        assert spread_with_slip > spread_no_slip


class TestSkipRate:
    def test_skip_rate(self, winning_trades):
        """Skip rate should produce different results from no skipping."""
        result_no_skip = run_monte_carlo(
            trades=winning_trades,
            n_simulations=500,
            skip_rate=0.0,
            seed=42,
        )
        result_with_skip = run_monte_carlo(
            trades=winning_trades,
            n_simulations=500,
            skip_rate=0.5,
            seed=42,
        )

        # Skipping ~50% of winning trades should reduce final P&L
        assert result_with_skip.median_pnl < result_no_skip.median_pnl

    def test_high_skip_rate(self):
        """Very high skip rate should reduce P&L substantially."""
        trades = [100.0] * 50
        result = run_monte_carlo(
            trades=trades,
            n_simulations=1000,
            skip_rate=0.9,
            seed=42,
        )

        # With 90% skip, expect roughly 5 trades * 100 = 500 final P&L
        assert result.median_pnl < 2500.0  # Much less than full 5000


class TestEmptyTrades:
    def test_empty_trades(self):
        """Empty trades list should return zero result without crashing."""
        result = run_monte_carlo(trades=[], n_simulations=100, seed=42)

        assert result.median_pnl == 0.0
        assert result.mean_pnl == 0.0
        assert result.pct_5_pnl == 0.0
        assert result.pct_95_pnl == 0.0
        assert result.median_max_dd == 0.0
        assert result.mean_max_dd == 0.0
        assert result.pass_rate == 0.0
        assert result.all_final_pnls == []
        assert result.all_max_drawdowns == []


class TestSingleTrade:
    def test_single_trade(self):
        """Single trade should work without error."""
        result = run_monte_carlo(
            trades=[100.0],
            n_simulations=500,
            profit_target=50.0,
            max_allowed_drawdown=200.0,
            seed=42,
        )

        # Single trade of 100 — P&L is always 100, no drawdown
        assert result.median_pnl == pytest.approx(100.0)
        assert result.mean_pnl == pytest.approx(100.0)
        assert result.pass_rate == 1.0

    def test_single_losing_trade(self):
        """Single losing trade should work without error."""
        result = run_monte_carlo(
            trades=[-100.0],
            n_simulations=500,
            profit_target=0.0,
            max_allowed_drawdown=50.0,
            seed=42,
        )

        assert result.median_pnl == pytest.approx(-100.0)
        assert result.pass_rate == 0.0


class TestHelperFunctions:
    def test_max_drawdown_no_drawdown(self):
        """Monotonically increasing curve has zero drawdown."""
        curve = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _compute_max_drawdown(curve) == 0.0

    def test_max_drawdown_simple(self):
        """Simple peak-to-trough test."""
        curve = np.array([0.0, 10.0, 5.0, 8.0, 3.0])
        # Peak is 10, trough after is 3 → drawdown = 7
        assert _compute_max_drawdown(curve) == pytest.approx(7.0)

    def test_max_drawdown_empty(self):
        assert _compute_max_drawdown(np.array([])) == 0.0

    def test_max_consecutive_losses(self):
        trades = np.array([10, -5, -3, -1, 20, -2, -8])
        assert _compute_max_consecutive_losses(trades) == 3

    def test_max_consecutive_losses_none(self):
        trades = np.array([10, 20, 30])
        assert _compute_max_consecutive_losses(trades) == 0

    def test_max_consecutive_losses_empty(self):
        assert _compute_max_consecutive_losses(np.array([])) == 0
