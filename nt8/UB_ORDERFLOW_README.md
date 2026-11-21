# UB Order-Flow Volume-Profile Strategy

Dedicated Ultra T-Bond (UB) strategy: `nt8/UBOrderFlowProfile.cs`, with a matching
Python backtester at `engine/ub_orderflow_backtest.py` (same rules, same defaults).

## The idea

Each RTH session (07:20–14:00 CT) builds a volume profile from real trades and splits
them into buy-aggressor and sell-aggressor volume (trade at ask = buy, at bid = sell).
The next day trades against the **prior** session's POC / VAH / VAL:

| Setup | Trigger | Order-flow confirmation | Stop | Target |
|---|---|---|---|---|
| **Rejection** (fade back into value) | Bar probes ≥ `ProbeTicks` beyond VAH/VAL, closes ≥ `CloseInsideTicks` back inside | **Delta flip**: bar delta against the probe (≥ `FlipDeltaRatio`) **or** **absorption**: heavy delta *with* the probe (≥ `AbsorbDeltaRatio`) but the bar closes in the opposite 40% of its range | Probe extreme + `StopBufferTicks` (clamped to `MinStopTicks`..`MaxStopTicks`) | Prior POC, only if reward ≥ `MinRR` × risk |
| **Acceptance** (breakout from value) | `AcceptBars` consecutive closes outside VA (fresh break) | Cumulative delta over those bars ≥ `AcceptDeltaRatio` in the break direction; no more than `AcceptMaxExtTicks` past the edge | `AcceptStopTicks` back inside the VA edge | `AcceptRR` × risk |

Each setup fires at most once per session. Risk controls: entries only between
07:35 and 13:30 CT (skips the 07:30 data releases), flatten at 13:55, max trades per day,
a daily $ loss limit, a consecutive-loss lockout and a kill switch.

## 1. Validate on your data first (Python)

Export data from NinjaTrader: **Tools → Historical Data → Export**, instrument UB,
type **Tick** (Last). Tick data is strongly preferred because it gives real bid/ask
delta. A 1-minute export works but delta is approximated, so results will be weaker
and won't match NT8.

```bash
cd engine
pip install -r requirements.txt

# NT8 exports are stamped in YOUR PC timezone; tell the backtester which one
python ub_orderflow_backtest.py --file "C:/path/UB 03-27.Last.txt" \
    --source-tz America/New_York --bar-minutes 5 --trades-csv ub_trades.csv

# parameter sweep: optimised on the first 70% of days, reported on the last 30%
python ub_orderflow_backtest.py --file "C:/path/UB 03-27.Last.txt" \
    --source-tz America/New_York --sweep

# test one setup on its own
python ub_orderflow_backtest.py --file ... --no-acceptance
```

Multiple contract months: concatenate the files (or use NT8's merged/back-adjusted
export). The output shows overall, per-setup, in-sample and out-of-sample stats.
**Only trust settings that hold up out-of-sample with ≥ ~100 trades.**

Costs modelled: 1 tick slippage per side on market and stop fills, no slippage on
target limits, $4.80 round-trip commission. If a bar touches both the stop and the
target, the stop is assumed to fill first.

## 2. Install in NinjaTrader 8

1. Copy `nt8/UBOrderFlowProfile.cs` to `Documents\NinjaTrader 8\bin\Custom\Strategies\`.
2. NinjaScript Editor → open it → **Compile** (F5).
3. Open a chart: front-month UB, **5 Minute**, default trading hours, and in Data
   Series tick **Tick Replay**. Load at least 2–3 days so a prior session exists.
4. Add the strategy and enter the parameters you validated in Python.
5. Run it in **Strategy Analyzer** (Tick Replay on) and compare it with the Python
   report. Then run it on **Sim101** for a few weeks before going live.

The chart draws the prior VAH (red), POC (gold) and VAL (green), with a status line
showing trades and day P&L.

## Known differences: NT8 vs Python

- Flatten: Python exits at the close of the 13:55 bar; NT8 exits at the next bar's open.
- Without Tick Replay, NT8's historical profile and delta use the same bar
  approximation as Python's `approx_clv` mode, so they are weak in both.
- Commission and slippage in NT8 come from your commission template and the
  `Slippage` setting.
