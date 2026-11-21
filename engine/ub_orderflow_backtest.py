"""
UB Order-Flow Volume-Profile Backtester
=======================================

Python twin of nt8/UBOrderFlowProfile.cs. Same rules, same defaults, so you can
validate / tune on your own data before running the strategy in NinjaTrader.

Strategy (all levels are from the PRIOR RTH session -> no lookahead):
  * Volume profile per RTH session (07:20-14:00 CT): POC, VAH, VAL (70% VA).
  * REJECTION (responsive): bar probes beyond VAH/VAL by >= ProbeTicks and closes
    back inside by >= CloseInsideTicks, confirmed by order flow:
        - delta flip   : bar delta ratio against the probe <= -FlipDeltaRatio, or
        - absorption   : aggressive delta WITH the probe >= AbsorbDeltaRatio but the
                         bar closes in the opposite 40% of its range.
    Target = prior POC, stop = probe extreme + StopBufferTicks.
  * ACCEPTANCE (initiative): AcceptBars consecutive closes outside value (fresh
    break), cumulative delta ratio over those bars >= AcceptDeltaRatio in the
    break direction, price not more than AcceptMaxExtTicks past the edge.
    Stop = AcceptStopTicks back inside the edge, target = AcceptRR x risk.
  * Risk: trade window, flatten time, max trades/day, daily $ loss limit,
    consecutive-loss lockout. Each setup fires at most once per level per session.

Input formats (auto-detected):
  * NT8 tick export   : yyyyMMdd HHmmss fffffff;last;bid;ask;volume   (best: real delta)
                        yyyyMMdd HHmmss fffffff;last;volume           (tick-rule delta)
  * NT8 minute export : yyyyMMdd HHmmss;open;high;low;close;volume    (approx delta)
  * CSV with header   : timestamp,open,high,low,close,volume[,buy_volume,sell_volume]

Usage:
    python ub_orderflow_backtest.py --file ../data/UB_ticks.txt --bar-minutes 5
    python ub_orderflow_backtest.py --file ../data/UB.csv --source-tz America/New_York
    python ub_orderflow_backtest.py --file ../data/UB_ticks.txt --sweep
    python ub_orderflow_backtest.py --synthetic            # smoke test, no data needed
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import dataclass, field, replace, asdict
from datetime import time as dtime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

TICK = 1.0 / 32.0          # UB tick size
TICK_VALUE = 31.25         # $ per tick per contract
CT = "America/Chicago"


# =============================================================================
# Parameters (keep defaults identical to the NT8 strategy)
# =============================================================================
@dataclass
class Params:
    rth_start: str = "07:20"
    rth_end: str = "14:00"
    trade_start: str = "07:35"      # skip 07:30 CT data releases
    trade_end: str = "13:30"        # no new entries after
    flatten: str = "13:55"
    value_area_pct: float = 0.70

    enable_rejection: bool = True
    probe_ticks: int = 1
    close_inside_ticks: int = 1
    flip_delta_ratio: float = 0.05
    absorb_delta_ratio: float = 0.15
    stop_buffer_ticks: int = 2
    min_stop_ticks: int = 4
    max_stop_ticks: int = 14
    min_rr: float = 1.0

    enable_acceptance: bool = True
    accept_bars: int = 3
    accept_delta_ratio: float = 0.08
    accept_max_ext_ticks: int = 10
    accept_stop_ticks: int = 8
    accept_rr: float = 1.5

    contracts: int = 1
    max_trades_day: int = 3
    max_daily_loss: float = 750.0
    max_consec_losses: int = 2

    slippage_ticks: int = 1          # per side on market/stop fills
    commission_rt: float = 4.80      # $ round trip per contract


def _t(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def price_to_idx(p: float) -> int:
    return int(round(p / TICK))


def idx_to_price(i: int) -> float:
    return i * TICK


# =============================================================================
# Volume profile
# =============================================================================
def value_area(profile: Dict[int, float], pct: float = 0.70) -> Optional[Tuple[int, int, int]]:
    """Return (poc, vah, val) tick indices. Identical algorithm to the C# version:
    POC = max volume (tie -> lower price). Expand from POC, comparing the sum of the
    next two levels above vs the next two below, add the larger (tie -> above)."""
    if not profile:
        return None
    total = sum(profile.values())
    if total <= 0:
        return None
    lo, hi = min(profile), max(profile)
    vols = [profile.get(i, 0.0) for i in range(lo, hi + 1)]
    poc_off = max(range(len(vols)), key=lambda k: (vols[k], -k))
    up = dn = poc_off
    acc = vols[poc_off]
    target = total * pct
    n = len(vols)
    while acc < target and (up < n - 1 or dn > 0):
        a = sum(vols[up + 1: min(up + 3, n)]) if up < n - 1 else -1.0
        b = sum(vols[max(dn - 2, 0): dn]) if dn > 0 else -1.0
        if a >= b:
            step = min(2, n - 1 - up)
            acc += sum(vols[up + 1: up + 1 + step])
            up += step
        else:
            step = min(2, dn)
            acc += sum(vols[dn - step: dn])
            dn -= step
    return lo + poc_off, lo + up, lo + dn


# =============================================================================
# Data loading
# =============================================================================
@dataclass
class Bars:
    df: pd.DataFrame                    # index: bar close time (CT, tz-naive)
    levels: List[Dict[int, float]]      # per-bar volume-at-price
    delta_quality: str                  # "bid_ask" | "tick_rule" | "approx_clv"


def _read_nt8_semicolon(path: Path) -> Tuple[str, pd.DataFrame]:
    with open(path, "r") as f:
        first = f.readline().strip()
    parts = first.split(";")
    ts_fields = parts[0].split(" ")
    if len(ts_fields) == 3:                         # tick export
        cols = (["ts", "last", "bid", "ask", "volume"] if len(parts) == 5
                else ["ts", "last", "volume"])
        df = pd.read_csv(path, sep=";", header=None, names=cols)
        ts = df["ts"].str.slice(0, 15) + "." + df["ts"].str.slice(16, 22)
        df["timestamp"] = pd.to_datetime(ts, format="%Y%m%d %H%M%S.%f")
        return "ticks", df.drop(columns=["ts"])
    df = pd.read_csv(path, sep=";", header=None,
                     names=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S")
    return "bars", df.drop(columns=["ts"])


def _read_csv_header(path: Path) -> Tuple[str, pd.DataFrame]:
    df = pd.read_csv(path)
    m = {}
    for c in df.columns:
        k = c.strip().lower().replace(" ", "_").replace("/", "_")
        if k in ("date", "datetime", "date_time", "time", "timestamp"):
            m[c] = "timestamp"
        elif k in ("open", "high", "low", "close", "volume", "bid", "ask"):
            m[c] = k
        elif k in ("last", "price"):
            m[c] = "last"
        elif k in ("buy_volume", "ask_volume", "buyvol"):
            m[c] = "buy_volume"
        elif k in ("sell_volume", "bid_volume", "sellvol"):
            m[c] = "sell_volume"
        elif k == "vol":
            m[c] = "volume"
    df = df.rename(columns=m)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    kind = "ticks" if "last" in df.columns and "open" not in df.columns else "bars"
    return kind, df


def load(path: str, source_tz: str = CT, bar_minutes: int = 5) -> Bars:
    p = Path(path)
    with open(p, "r") as f:
        first = f.readline()
    kind, raw = (_read_nt8_semicolon(p) if ";" in first and not first[0].isalpha()
                 else _read_csv_header(p))
    ts = raw["timestamp"]
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT")
    raw["timestamp"] = ts.dt.tz_convert(CT).dt.tz_localize(None)
    raw = raw.dropna(subset=["timestamp"]).sort_values("timestamp", kind="stable")
    if kind == "ticks":
        return bars_from_ticks(raw, bar_minutes)
    return bars_from_bars(raw)


def classify_ticks(t: pd.DataFrame) -> Tuple[np.ndarray, str]:
    """+1 buy aggressor, -1 sell aggressor. Bid/ask if available, else tick rule."""
    px = t["last"].to_numpy(float)
    diff = np.sign(np.diff(px, prepend=px[0]))
    s = pd.Series(diff).replace(0, np.nan).ffill().fillna(1).to_numpy()
    if "bid" in t.columns and "ask" in t.columns:
        bid, ask = t["bid"].to_numpy(float), t["ask"].to_numpy(float)
        side = np.where(px >= ask, 1.0, np.where(px <= bid, -1.0, s))
        return side, "bid_ask"
    return s, "tick_rule"


def bars_from_ticks(t: pd.DataFrame, bar_minutes: int) -> Bars:
    side, quality = classify_ticks(t)
    t = t.assign(side=side, idx=np.rint(t["last"].to_numpy(float) / TICK).astype(int))
    # NT8 convention: bar timestamp = close time; tick at exactly hh:mm:00 belongs to it
    t["bar"] = t["timestamp"].dt.ceil(f"{bar_minutes}min")
    t["buy"] = np.where(t["side"] > 0, t["volume"], 0.0)
    t["sell"] = np.where(t["side"] < 0, t["volume"], 0.0)
    g = t.groupby("bar", sort=True)
    df = pd.DataFrame({
        "open": g["last"].first(), "high": g["last"].max(), "low": g["last"].min(),
        "close": g["last"].last(), "volume": g["volume"].sum(),
        "buy_volume": g["buy"].sum(), "sell_volume": g["sell"].sum(),
    })
    lv = t.groupby(["bar", "idx"], sort=True)["volume"].sum()
    levels_map: Dict = {}
    for (b, i), v in lv.items():
        levels_map.setdefault(b, {})[int(i)] = float(v)
    levels = [levels_map[b] for b in df.index]
    return Bars(df, levels, quality)


def bars_from_bars(b: pd.DataFrame) -> Bars:
    df = b.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)
    if "buy_volume" in b.columns and "sell_volume" in b.columns:
        df["buy_volume"] = b["buy_volume"].to_numpy(float)
        df["sell_volume"] = b["sell_volume"].to_numpy(float)
        quality = "bid_ask"
    else:
        # Close-location approximation: weak proxy for real delta.
        rng = (df["high"] - df["low"]).to_numpy()
        clv = np.where(rng > 0, (2 * (df["close"] - df["low"]).to_numpy() - rng) / np.where(rng > 0, rng, 1), 0.0)
        d = clv * df["volume"].to_numpy()
        df["buy_volume"] = (df["volume"] + d) / 2
        df["sell_volume"] = (df["volume"] - d) / 2
        quality = "approx_clv"
    levels = []
    for h, l, v in zip(df["high"], df["low"], df["volume"]):
        lo, hi = price_to_idx(l), price_to_idx(h)
        n = hi - lo + 1
        levels.append({i: v / n for i in range(lo, hi + 1)})
    return Bars(df, levels, quality)


# =============================================================================
# Backtest
# =============================================================================
@dataclass
class Trade:
    setup: str
    direction: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    exit_time: Optional[pd.Timestamp] = None
    exit: Optional[float] = None
    reason: str = ""
    pnl: float = 0.0


@dataclass
class Signal:
    setup: str
    direction: int
    stop: float
    target: float


def evaluate_signal(p: Params, o, h, l, c, buy, sell, closes_hist, deltas_hist, vols_hist,
                    lv: Dict[str, float], used: Dict[str, bool]) -> Optional[Signal]:
    """Pure signal function on the just-closed bar. Mirrors EvaluateSignals() in C#."""
    vah, val, poc = lv["vah"], lv["val"], lv["poc"]
    vol = buy + sell
    if vol <= 0:
        return None
    dr = (buy - sell) / vol                      # bar delta ratio
    rng = h - l
    clv = (c - l) / rng if rng > 0 else 0.5      # 0 = closed on low, 1 = on high

    if p.enable_rejection:
        # Short: probe above VAH, close back inside
        if (not used["rej_short"] and h >= vah + p.probe_ticks * TICK
                and c <= vah - p.close_inside_ticks * TICK and c > poc):
            flip = dr <= -p.flip_delta_ratio
            absorb = dr >= p.absorb_delta_ratio and clv <= 0.4
            if flip or absorb:
                stop = h + p.stop_buffer_ticks * TICK
                risk = (stop - c) / TICK
                if risk < p.min_stop_ticks:
                    stop = c + p.min_stop_ticks * TICK
                    risk = p.min_stop_ticks
                reward = (c - poc) / TICK
                if risk <= p.max_stop_ticks and reward >= p.min_rr * risk:
                    used["rej_short"] = True
                    return Signal("REJ_SHORT", -1, stop, poc)
        # Long: probe below VAL, close back inside
        if (not used["rej_long"] and l <= val - p.probe_ticks * TICK
                and c >= val + p.close_inside_ticks * TICK and c < poc):
            flip = dr >= p.flip_delta_ratio
            absorb = dr <= -p.absorb_delta_ratio and clv >= 0.6
            if flip or absorb:
                stop = l - p.stop_buffer_ticks * TICK
                risk = (c - stop) / TICK
                if risk < p.min_stop_ticks:
                    stop = c - p.min_stop_ticks * TICK
                    risk = p.min_stop_ticks
                reward = (poc - c) / TICK
                if risk <= p.max_stop_ticks and reward >= p.min_rr * risk:
                    used["rej_long"] = True
                    return Signal("REJ_LONG", 1, stop, poc)

    if p.enable_acceptance and len(closes_hist) > p.accept_bars:
        n = p.accept_bars
        recent = closes_hist[-n:]
        prior = closes_hist[-n - 1]
        sv = sum(vols_hist[-n:])
        cdr = sum(deltas_hist[-n:]) / sv if sv > 0 else 0.0
        if (not used["acc_long"] and all(x > vah for x in recent) and prior <= vah
                and cdr >= p.accept_delta_ratio and (c - vah) / TICK <= p.accept_max_ext_ticks):
            stop = vah - p.accept_stop_ticks * TICK
            risk = c - stop
            used["acc_long"] = True
            return Signal("ACC_LONG", 1, stop, c + p.accept_rr * risk)
        if (not used["acc_short"] and all(x < val for x in recent) and prior >= val
                and cdr <= -p.accept_delta_ratio and (val - c) / TICK <= p.accept_max_ext_ticks):
            stop = val + p.accept_stop_ticks * TICK
            risk = stop - c
            used["acc_short"] = True
            return Signal("ACC_SHORT", -1, stop, c - p.accept_rr * risk)
    return None


def backtest(bars: Bars, p: Params) -> List[Trade]:
    df = bars.df
    times = df.index
    O, H, L, C = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    B, S = df["buy_volume"].to_numpy(float), df["sell_volume"].to_numpy(float)
    rth_s, rth_e = _t(p.rth_start), _t(p.rth_end)
    tr_s, tr_e, flat_t = _t(p.trade_start), _t(p.trade_end), _t(p.flatten)
    slip = p.slippage_ticks * TICK

    trades: List[Trade] = []
    prior_lv: Optional[Dict[str, float]] = None
    cur_profile: Dict[int, float] = {}
    cur_date = None
    in_rth_prev = False
    used = {}
    closes, deltas, vols = [], [], []
    day_pnl, day_trades, consec = 0.0, 0, 0
    pending: Optional[Signal] = None
    pos: Optional[Trade] = None

    def close_pos(tr: Trade, t, px, reason):
        nonlocal day_pnl, consec, pos
        tr.exit_time, tr.exit, tr.reason = t, px, reason
        ticks = (px - tr.entry) / TICK * tr.direction
        tr.pnl = ticks * TICK_VALUE * p.contracts - p.commission_rt * p.contracts
        day_pnl += tr.pnl
        consec = consec + 1 if tr.pnl < 0 else 0
        trades.append(tr)
        pos = None

    for i in range(len(df)):
        t = times[i]
        tt = t.time()
        in_rth = rth_s < tt <= rth_e

        # ---- session roll: first RTH bar of a new day finalizes prior profile
        if in_rth and (not in_rth_prev or t.date() != cur_date):
            if cur_profile:
                va = value_area(cur_profile, p.value_area_pct)
                if va:
                    prior_lv = {"poc": idx_to_price(va[0]), "vah": idx_to_price(va[1]),
                                "val": idx_to_price(va[2])}
            cur_profile = {}
            cur_date = t.date()
            used = {k: False for k in ("rej_short", "rej_long", "acc_long", "acc_short")}
            closes, deltas, vols = [], [], []
            day_pnl, day_trades, consec = 0.0, 0, 0
            pending = None
        in_rth_prev = in_rth

        # ---- fill pending entry at this bar's open
        if pending is not None and pos is None:
            d = pending.direction
            entry = O[i] + d * slip
            pos = Trade(pending.setup, d, times[i - 1], t, entry, pending.stop, pending.target)
            day_trades += 1
            pending = None
            # gap through stop at open
            if (d > 0 and O[i] <= pos.stop) or (d < 0 and O[i] >= pos.stop):
                close_pos(pos, t, O[i] - d * slip, "stop_gap")

        # ---- manage open position on this bar (stop first if both touched)
        if pos is not None:
            d = pos.direction
            hit_stop = L[i] <= pos.stop if d > 0 else H[i] >= pos.stop
            hit_tgt = H[i] >= pos.target if d > 0 else L[i] <= pos.target
            if hit_stop:
                close_pos(pos, t, pos.stop - d * slip, "stop")
            elif hit_tgt:
                close_pos(pos, t, pos.target, "target")
            elif tt >= flat_t or not in_rth:
                close_pos(pos, t, C[i] - d * slip, "flatten")

        if not in_rth:
            continue

        for k, v in bars.levels[i].items():
            cur_profile[k] = cur_profile.get(k, 0.0) + v
        closes.append(C[i]); deltas.append(B[i] - S[i]); vols.append(B[i] + S[i])

        if pos is not None or prior_lv is None:
            continue
        if not (tr_s <= tt <= tr_e):
            continue
        if (day_trades >= p.max_trades_day or day_pnl <= -p.max_daily_loss
                or consec >= p.max_consec_losses):
            continue
        sig = evaluate_signal(p, O[i], H[i], L[i], C[i], B[i], S[i],
                              closes, deltas, vols, prior_lv, used)
        if sig is not None and i + 1 < len(df) and times[i + 1].date() == t.date():
            pending = sig

    if pos is not None:
        close_pos(pos, times[-1], C[-1], "eod_data")
    return trades


# =============================================================================
# Reporting
# =============================================================================
def stats(trades: List[Trade]) -> Dict[str, float]:
    if not trades:
        return {"trades": 0, "net": 0.0, "win_rate": 0.0, "pf": 0.0, "avg": 0.0,
                "max_dd": 0.0, "sharpe_daily": 0.0}
    pnl = np.array([t.pnl for t in trades])
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    dd = (np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()
    daily = pd.Series(pnl, index=[t.entry_time.date() for t in trades]).groupby(level=0).sum()
    sh = daily.mean() / daily.std() * math.sqrt(252) if len(daily) > 1 and daily.std() > 0 else 0.0
    return {"trades": len(trades), "net": float(pnl.sum()),
            "win_rate": float((pnl > 0).mean()),
            "pf": float(wins / losses) if losses > 0 else float("inf"),
            "avg": float(pnl.mean()), "max_dd": float(dd), "sharpe_daily": float(sh)}


def fmt(s: Dict[str, float]) -> str:
    return (f"trades={s['trades']:4d}  net=${s['net']:>10,.2f}  win={s['win_rate']:.1%}  "
            f"PF={s['pf']:.2f}  avg=${s['avg']:>7.2f}  maxDD=${s['max_dd']:>9,.2f}  "
            f"Sharpe(d)={s['sharpe_daily']:.2f}")


def split_bars(bars: Bars, frac: float) -> Tuple[Bars, Bars]:
    dates = sorted(set(bars.df.index.date))
    cut = dates[int(len(dates) * frac)] if len(dates) > 1 else dates[-1]
    m = np.array([d < cut for d in bars.df.index.date])
    a = Bars(bars.df[m], [x for x, k in zip(bars.levels, m) if k], bars.delta_quality)
    b = Bars(bars.df[~m], [x for x, k in zip(bars.levels, m) if not k], bars.delta_quality)
    return a, b


def report(bars: Bars, p: Params, is_frac: float = 0.7, out_csv: Optional[str] = None):
    print(f"\nBars: {len(bars.df):,}  {bars.df.index[0]} -> {bars.df.index[-1]}  "
          f"delta source: {bars.delta_quality}")
    if bars.delta_quality == "approx_clv":
        print("  WARNING: no bid/ask data -> delta is approximated from close location.\n"
              "  Results will NOT match the NT8 strategy with Tick Replay. Export tick data.")
    trades = backtest(bars, p)
    print("\nALL     ", fmt(stats(trades)))
    for setup in ("REJ_LONG", "REJ_SHORT", "ACC_LONG", "ACC_SHORT"):
        sub = [t for t in trades if t.setup == setup]
        print(f"{setup:9s}", fmt(stats(sub)))
    is_b, oos_b = split_bars(bars, is_frac)
    print(f"\nIn-sample  ({is_frac:.0%})", fmt(stats(backtest(is_b, p))))
    print(f"Out-sample ({1 - is_frac:.0%})", fmt(stats(backtest(oos_b, p))))
    if out_csv:
        pd.DataFrame([asdict(t) for t in trades]).to_csv(out_csv, index=False)
        print(f"\nTrades written to {out_csv}")
    return trades


SWEEP_GRID = {
    "probe_ticks": [1, 2],
    "absorb_delta_ratio": [0.10, 0.15, 0.25],
    "stop_buffer_ticks": [1, 2, 3],
    "accept_bars": [2, 3, 4],
    "accept_delta_ratio": [0.05, 0.08, 0.12],
    "accept_rr": [1.0, 1.5, 2.0],
}


def sweep(bars: Bars, base: Params, is_frac: float = 0.7, top: int = 10, min_trades: int = 30):
    """Grid search on IN-SAMPLE only; reports OOS for the top sets. Pick robust
    neighbourhoods, not the single best row."""
    is_b, oos_b = split_bars(bars, is_frac)
    keys = list(SWEEP_GRID)
    rows = []
    for combo in itertools.product(*SWEEP_GRID.values()):
        p = replace(base, **dict(zip(keys, combo)))
        s = stats(backtest(is_b, p))
        if s["trades"] >= min_trades:
            rows.append((s["pf"] if math.isfinite(s["pf"]) else 99, s["net"], combo, s))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    print(f"\nSweep: {len(rows)} sets with >= {min_trades} IS trades. Top {top} by IS PF:")
    for pf, net, combo, s in rows[:top]:
        p = replace(base, **dict(zip(keys, combo)))
        o = stats(backtest(oos_b, p))
        print(dict(zip(keys, combo)))
        print("   IS ", fmt(s))
        print("   OOS", fmt(o))


# =============================================================================
# Synthetic data (smoke testing only — NOT evidence of an edge)
# =============================================================================
def synthetic_ticks(days: int = 30, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    px_idx = price_to_idx(120.0)
    start = pd.Timestamp("2026-01-05")
    d = 0
    while d < days:
        day = start + pd.Timedelta(days=d)
        d += 1
        if day.weekday() >= 5:
            continue
        anchor = px_idx
        t = day + pd.Timedelta(hours=7, minutes=20, seconds=1)
        end = day + pd.Timedelta(hours=14)
        while t < end:
            # mean-reverting walk around a daily anchor with occasional drift
            pull = -0.02 * (px_idx - anchor)
            step = int(np.sign(rng.normal(pull, 1.0)))
            px_idx += step
            if rng.random() < 0.002:
                anchor += int(rng.integers(-12, 13))
            vol = int(rng.integers(1, 30))
            bid, ask = px_idx * TICK, (px_idx + 1) * TICK
            last = ask if step > 0 or (step == 0 and rng.random() < 0.5) else bid
            rows.append((t, last, bid, ask, vol))
            t += pd.Timedelta(seconds=float(rng.exponential(4.0)))
    return pd.DataFrame(rows, columns=["timestamp", "last", "bid", "ask", "volume"])


def main():
    ap = argparse.ArgumentParser(description="UB order-flow volume-profile backtester")
    ap.add_argument("--file", help="NT8 tick/minute export or CSV")
    ap.add_argument("--synthetic", action="store_true", help="run on synthetic ticks")
    ap.add_argument("--source-tz", default=CT,
                    help="timezone of timestamps in the file (NT8 exports use your PC timezone)")
    ap.add_argument("--bar-minutes", type=int, default=5, help="bar size when building from ticks")
    ap.add_argument("--is-frac", type=float, default=0.7)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--trades-csv", default=None)
    ap.add_argument("--contracts", type=int, default=1)
    ap.add_argument("--no-rejection", action="store_true")
    ap.add_argument("--no-acceptance", action="store_true")
    a = ap.parse_args()

    p = Params(contracts=a.contracts, enable_rejection=not a.no_rejection,
               enable_acceptance=not a.no_acceptance)
    if a.synthetic:
        bars = bars_from_ticks(synthetic_ticks(), a.bar_minutes)
    elif a.file:
        bars = load(a.file, a.source_tz, a.bar_minutes)
    else:
        ap.error("--file or --synthetic required")
    report(bars, p, a.is_frac, a.trades_csv)
    if a.sweep:
        sweep(bars, p, a.is_frac)


if __name__ == "__main__":
    main()
