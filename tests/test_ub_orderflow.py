"""Tests for the UB order-flow volume-profile backtester."""

import numpy as np
import pandas as pd
import pytest

import ub_orderflow_backtest as ub
from ub_orderflow_backtest import TICK, Params


def test_value_area_symmetric():
    prof = {100: 10, 101: 20, 102: 50, 103: 20, 104: 10}
    poc, vah, val = ub.value_area(prof, 0.70)
    assert poc == 102
    assert val <= 102 <= vah
    covered = sum(v for k, v in prof.items() if val <= k <= vah)
    assert covered >= 0.70 * sum(prof.values())


def test_value_area_poc_tie_picks_lower_price():
    poc, _, _ = ub.value_area({10: 5, 11: 5}, 0.7)
    assert poc == 10


def test_value_area_single_level_and_empty():
    assert ub.value_area({50: 3}) == (50, 50, 50)
    assert ub.value_area({}) is None


def test_classify_bid_ask_and_tick_rule():
    t = pd.DataFrame({"last": [100.0, 100.03125, 100.0, 100.015],
                      "bid": [100.0, 100.0, 100.0, 100.0],
                      "ask": [100.03125] * 4})
    side, q = ub.classify_ticks(t)
    assert q == "bid_ask"
    assert list(side[:3]) == [-1, 1, -1]
    side2, q2 = ub.classify_ticks(t[["last"]])
    assert q2 == "tick_rule"
    assert side2[1] == 1 and side2[2] == -1


def test_nt8_tick_export_parsing(tmp_path):
    f = tmp_path / "UB.Last.txt"
    f.write_text(
        "20260105 072030 1000000;120;119.96875;120;5\n"
        "20260105 072100 0000000;120.03125;120;120.03125;3\n"
        "20260105 072200 5000000;119.96875;119.96875;120;7\n")
    bars = ub.load(str(f), source_tz="America/Chicago", bar_minutes=1)
    assert bars.delta_quality == "bid_ask"
    # 07:21:00.000 belongs to the 07:21 bar (NT8 close-time convention)
    assert list(bars.df.index) == [pd.Timestamp("2026-01-05 07:21:00"),
                                   pd.Timestamp("2026-01-05 07:23:00")]
    assert bars.df["buy_volume"].iloc[0] == 8 and bars.df["sell_volume"].iloc[1] == 7


def test_nt8_minute_export_parsing_and_tz(tmp_path):
    f = tmp_path / "UB.txt"
    f.write_text("20260105 092500;120;120.0625;119.96875;120.03125;400\n")
    bars = ub.load(str(f), source_tz="America/New_York")
    assert bars.df.index[0] == pd.Timestamp("2026-01-05 08:25:00")   # ET -> CT
    assert bars.delta_quality == "approx_clv"
    assert sum(bars.levels[0].values()) == pytest.approx(400)


def _bar_frame(rows):
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "buy", "sell"])
    df = df.set_index("timestamp")
    out = df[["open", "high", "low", "close"]].copy()
    out["buy_volume"], out["sell_volume"] = df["buy"], df["sell"]
    out["volume"] = df["buy"] + df["sell"]
    levels = []
    for h, l, v in zip(out["high"], out["low"], out["volume"]):
        lo, hi = ub.price_to_idx(l), ub.price_to_idx(h)
        levels.append({i: v / (hi - lo + 1) for i in range(lo, hi + 1)})
    return ub.Bars(out, levels, "bid_ask")


def _day1(day="2026-01-05"):
    """Prior session: wide balanced range with a volume peak at 120."""
    rows, t = [], pd.Timestamp(f"{day} 07:25")
    for k in range(30):
        if k % 2:
            lo = hi = 120.0
        else:
            lo, hi = 119.5, 120.5
        rows.append((t, 120, hi, lo, 120, 500, 500))
        t += pd.Timedelta(minutes=5)
    return rows


def _prior_levels():
    prof = {}
    for lv in _bar_frame(_day1()).levels:
        for k, v in lv.items():
            prof[k] = prof.get(k, 0) + v
    return [ub.idx_to_price(x) for x in ub.value_area(prof)]


def _probe_day(after_rows):
    poc, vah, _ = _prior_levels()
    assert poc == 120.0 and vah > poc + 4 * TICK
    rows = _day1()
    t = pd.Timestamp("2026-01-06 07:25")
    rows.append((t, 120, 120.0625, 119.9375, 120, 100, 100))
    t += pd.Timedelta(minutes=10)                           # 07:35 trade window open
    probe_hi = vah + 3 * TICK
    close = vah - 2 * TICK
    # probe above VAH, close back inside, sellers dominate (delta flip)
    rows.append((t, vah, probe_hi, close - TICK, close, 100, 400))
    rows += after_rows(t, close)
    return _bar_frame(rows), probe_hi


def test_rejection_short_fires_and_targets_prior_poc():
    def after(t, close):
        return [(t + pd.Timedelta(minutes=5 * k), close, close + TICK, 119.96875, 119.96875 + TICK, 200, 200)
                for k in range(1, 6)]
    bars, probe_hi = _probe_day(after)
    p = Params(enable_acceptance=False, min_rr=0.1)
    trades = ub.backtest(bars, p)
    assert len(trades) == 1
    tr = trades[0]
    assert tr.setup == "REJ_SHORT" and tr.direction == -1
    assert tr.reason == "target" and tr.target == 120.0
    assert tr.stop == pytest.approx(probe_hi + p.stop_buffer_ticks * TICK)
    assert tr.entry_time > tr.signal_time                   # filled on NEXT bar


def test_stop_wins_when_bar_touches_both():
    def after(t, close):
        return [(t + pd.Timedelta(minutes=5), close, 121.0, 119.0, 120.0, 300, 300),
                (t + pd.Timedelta(minutes=10), 120.0, 120.03125, 119.96875, 120.0, 10, 10)]
    bars, _ = _probe_day(after)
    trades = ub.backtest(bars, Params(enable_acceptance=False, min_rr=0.1))
    assert len(trades) == 1 and trades[0].reason == "stop" and trades[0].pnl < 0


def test_no_trades_on_first_session_no_lookahead():
    rows = _day1()
    trades = ub.backtest(_bar_frame(rows), Params())
    assert trades == []


def test_daily_loss_limit_blocks_trading():
    bars = ub.bars_from_ticks(ub.synthetic_ticks(days=20), 5)
    p = Params(max_daily_loss=1.0, max_trades_day=10, max_consec_losses=10)
    trades = ub.backtest(bars, p)
    by_day = {}
    for tr in trades:
        by_day.setdefault(tr.entry_time.date(), []).append(tr)
    for day_trades in by_day.values():
        # once a trade loses, nothing else is opened that day
        for k, tr in enumerate(day_trades[:-1]):
            assert tr.pnl > 0 or k == len(day_trades) - 1


def test_synthetic_smoke_and_flatten_time():
    bars = ub.bars_from_ticks(ub.synthetic_ticks(days=25), 5)
    trades = ub.backtest(bars, Params())
    assert len(trades) > 0
    for tr in trades:
        assert tr.exit_time.time() <= pd.Timestamp("14:00").time()
        assert tr.entry_time.time() >= pd.Timestamp("07:35").time()
    s = ub.stats(trades)
    assert s["trades"] == len(trades)
