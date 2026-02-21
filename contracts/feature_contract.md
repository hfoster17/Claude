# Feature Vector Contract v2

## Overview
All components (NT8 strategy, Python engine, training pipeline) MUST compute features identically.

## Feature Vector Definition (6 features, index 0–5)

| Index | Name             | Formula                                       | Normalization               |
|-------|------------------|-----------------------------------------------|-----------------------------|
| 0     | log_return       | `ln(Close[0] / Close[1])`                     | Z-score (rolling 100-bar)   |
| 1     | realized_vol     | `std(log_returns[0..19], ddof=1)`              | Z-score (rolling 100-bar)   |
| 2     | rsi_deviation    | `(RSI(14) - 50.0) / 50.0`                     | Raw (bounded [-1, 1])       |
| 3     | vwap_distance    | `(Close - VWAP) / ATR(14)`                    | Clipped [-3, 3]             |
| 4     | bar_range_ratio  | `(High - Low) / ATR(14)`                      | Clipped [0, 5]              |
| 5     | volume_zscore    | `(Volume - mean(Vol,20)) / std(Vol,20,ddof=1)`| Clipped [-3, 3]             |

## Detailed Calculation Rules

### Feature 0 — Log Return
```
raw = ln(Close[0] / Close[1])
mean_100 = rolling_mean(raw, 100)
std_100  = rolling_std(raw, 100, ddof=1)
feature[0] = (raw - mean_100) / max(std_100, 1e-10)
```

### Feature 1 — Realized Volatility
```
log_rets = [ln(Close[i] / Close[i+1]) for i in 0..19]
raw = std(log_rets, ddof=1)
mean_100 = rolling_mean(raw, 100)
std_100  = rolling_std(raw, 100, ddof=1)
feature[1] = (raw - mean_100) / max(std_100, 1e-10)
```

### Feature 2 — RSI Deviation
```
rsi_14 = standard Wilder RSI with period 14
feature[2] = (rsi_14 - 50.0) / 50.0
```
No further normalization. Output is in [-1, 1].

### Feature 3 — VWAP Distance
```
vwap = cumulative(price * volume) / cumulative(volume)  (reset each session)
atr_14 = ATR(14)  (standard Wilder smoothing)
raw = (Close - vwap) / max(atr_14, 1e-10)
feature[3] = clip(raw, -3.0, 3.0)
```

### Feature 4 — Bar Range Ratio
```
atr_14 = ATR(14)
raw = (High - Low) / max(atr_14, 1e-10)
feature[4] = clip(raw, 0.0, 5.0)
```

### Feature 5 — Volume Z-Score
```
mean_vol_20 = rolling_mean(Volume, 20)
std_vol_20  = rolling_std(Volume, 20, ddof=1)
raw = (Volume - mean_vol_20) / max(std_vol_20, 1e-10)
feature[5] = clip(raw, -3.0, 3.0)
```

## Edge Case Rules

1. **Division by zero**: If denominator < 1e-10, use 1e-10.
2. **NaN/Inf**: Replace with 0.0.
3. **Warmup period**: Use `min(available_bars, window)` for rolling calculations. Do not emit signals until at least 100 bars available.
4. **Zero volume bar**: Volume features use 0.0.
5. **Flat price (Close == previous Close)**: log_return = 0.0.
6. **Session VWAP reset**: VWAP resets at session open. Before first full bar of session, use close as VWAP proxy.

## Order Flow Confirmation (NT8 Only)

Order flow is used as a **trade confirmation gate** — it does not generate signals, only confirms or denies signals produced by the HMM regime model.

### Metrics

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| Cumulative Delta | `sum(buy_volume - sell_volume)` since session open | Directional conviction |
| Per-Bar Delta | `bar_buy_volume - bar_sell_volume` | Short-term flow direction |
| Volume Imbalance | `(buy_vol - sell_vol) / (buy_vol + sell_vol)` per bar | Normalized flow bias |
| Large Orders | Trades with size > `avg_size * multiplier` | Institutional activity |

### Trade Classification

Trades are classified as buy or sell using the trade-at-bid/ask method:
- `price >= ask` → Buy (aggressor lifting the offer)
- `price <= bid` → Sell (aggressor hitting the bid)
- Between bid and ask → Split 50/50

### Confirmation Logic

Given a regime signal direction (+1 long, -1 short):
1. **Delta Z-Score**: Rolling delta should align with signal direction (z-score > threshold)
2. **Volume Imbalance**: Last bar imbalance should align (ratio > threshold)
3. **Decision**: At least one metric must confirm, and neither can deny
   - Both confirm or one confirms without denial → `Confirm` (allow trade)
   - Both deny → `Deny` (block trade)
   - Mixed or insufficient data → `Neutral` (allow trade)

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OrderFlowLookbackBars` | 10 | Number of bars for delta z-score calculation |
| `DeltaConfirmationThreshold` | 1.5 | Z-score threshold for delta confirmation |
| `ImbalanceConfirmationThreshold` | 0.15 | Volume imbalance ratio threshold |
| `LargeOrderMultiplier` | 3.0 | Multiplier of average trade size for large order detection |

## Parity Verification

To verify NT8 and Python produce identical features:
1. Export bar data from NT8 (OHLCV + timestamp)
2. Compute features in Python using `feature_engine.py`
3. Compare: all features must match within tolerance of 1e-6
