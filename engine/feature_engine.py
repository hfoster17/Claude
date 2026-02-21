"""
Feature Engine — computes the 6-feature observation vector.
Must produce identical results to the NT8 FeatureEngine.
See contracts/feature_contract.md for specification.
"""

import math
from collections import deque
from typing import List, Optional

import numpy as np

N_FEATURES = 6
WARMUP_BARS = 100
VARIANCE_FLOOR = 1e-10


class RollingStats:
    """Incremental rolling mean and standard deviation."""

    def __init__(self, window: int):
        self.window = window
        self._buf: deque = deque(maxlen=window)

    def push(self, value: float) -> None:
        self._buf.append(value)

    @property
    def count(self) -> int:
        return len(self._buf)

    def mean(self) -> float:
        if not self._buf:
            return 0.0
        return sum(self._buf) / len(self._buf)

    def std(self, ddof: int = 1) -> float:
        n = len(self._buf)
        if n < max(2, ddof + 1):
            return 0.0
        m = self.mean()
        var = sum((x - m) ** 2 for x in self._buf) / (n - ddof)
        return math.sqrt(max(var, 0.0))


class RSICalculator:
    """Wilder-smoothed RSI(14)."""

    def __init__(self, period: int = 14):
        self.period = period
        self._gains: List[float] = []
        self._losses: List[float] = []
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._count = 0
        self.value: float = 50.0

    def update(self, close: float) -> float:
        if self._prev_close is not None:
            change = close - self._prev_close
            gain = max(change, 0.0)
            loss = max(-change, 0.0)

            if self._count < self.period:
                self._gains.append(gain)
                self._losses.append(loss)
                self._count += 1

                if self._count == self.period:
                    self._avg_gain = sum(self._gains) / self.period
                    self._avg_loss = sum(self._losses) / self.period
            else:
                self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
                self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

            if self._avg_gain is not None:
                if self._avg_loss < VARIANCE_FLOOR:
                    self.value = 100.0 if self._avg_gain > 0 else 50.0
                else:
                    rs = self._avg_gain / self._avg_loss
                    self.value = 100.0 - (100.0 / (1.0 + rs))

        self._prev_close = close
        return self.value


class ATRCalculator:
    """Wilder-smoothed ATR(14)."""

    def __init__(self, period: int = 14):
        self.period = period
        self._tr_values: List[float] = []
        self._atr: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._count = 0
        self.value: float = 0.0

    def update(self, high: float, low: float, close: float) -> float:
        if self._prev_close is not None:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )
        else:
            tr = high - low

        if self._count < self.period:
            self._tr_values.append(tr)
            self._count += 1
            if self._count == self.period:
                self._atr = sum(self._tr_values) / self.period
        else:
            self._atr = (self._atr * (self.period - 1) + tr) / self.period

        if self._atr is not None:
            self.value = self._atr
        else:
            self.value = tr

        self._prev_close = close
        return self.value


class FeatureEngine:
    """
    Computes the 6-feature observation vector per bar.
    Feed bars sequentially via update(). Retrieve via get_features().
    """

    def __init__(self, vol_window: int = 20, zscore_window: int = 100):
        self.vol_window = vol_window
        self.zscore_window = zscore_window

        # Sub-calculators
        self._rsi = RSICalculator(14)
        self._atr = ATRCalculator(14)

        # Rolling buffers
        self._log_returns: deque = deque(maxlen=vol_window)
        self._ret_stats = RollingStats(zscore_window)
        self._vol_stats = RollingStats(zscore_window)
        self._vol_buf: deque = deque(maxlen=vol_window)

        # VWAP state (reset per session)
        self._cum_pv: float = 0.0
        self._cum_vol: float = 0.0

        self._prev_close: Optional[float] = None
        self._bar_count: int = 0
        self._features: np.ndarray = np.zeros(N_FEATURES)

    def reset_session(self) -> None:
        """Call at session open to reset VWAP accumulator."""
        self._cum_pv = 0.0
        self._cum_vol = 0.0

    @property
    def ready(self) -> bool:
        return self._bar_count >= WARMUP_BARS

    def update(
        self,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        session_reset: bool = False,
    ) -> np.ndarray:
        """
        Process one bar and return the 6-feature vector.
        """
        if session_reset:
            self.reset_session()

        self._bar_count += 1

        # ATR and RSI
        atr_val = self._atr.update(high, low, close)
        rsi_val = self._rsi.update(close)

        # Feature 0: Log Return (z-scored)
        if self._prev_close is not None and self._prev_close > 0:
            log_ret = math.log(close / self._prev_close)
        else:
            log_ret = 0.0
        self._ret_stats.push(log_ret)
        ret_mean = self._ret_stats.mean()
        ret_std = max(self._ret_stats.std(), VARIANCE_FLOOR)
        feat_0 = (log_ret - ret_mean) / ret_std

        # Feature 1: Realized Volatility (z-scored)
        self._log_returns.append(log_ret)
        if len(self._log_returns) >= 2:
            rv = float(np.std(list(self._log_returns), ddof=1))
        else:
            rv = 0.0
        self._vol_stats.push(rv)
        vol_mean = self._vol_stats.mean()
        vol_std = max(self._vol_stats.std(), VARIANCE_FLOOR)
        feat_1 = (rv - vol_mean) / vol_std

        # Feature 2: RSI Deviation
        feat_2 = (rsi_val - 50.0) / 50.0

        # Feature 3: VWAP Distance
        typical = (high + low + close) / 3.0
        self._cum_pv += typical * volume
        self._cum_vol += volume
        vwap = self._cum_pv / max(self._cum_vol, VARIANCE_FLOOR)
        safe_atr = max(atr_val, VARIANCE_FLOOR)
        feat_3 = np.clip((close - vwap) / safe_atr, -3.0, 3.0)

        # Feature 4: Bar Range Ratio
        feat_4 = np.clip((high - low) / safe_atr, 0.0, 5.0)

        # Feature 5: Volume Z-Score
        self._vol_buf.append(volume)
        if len(self._vol_buf) >= 2:
            vmean = float(np.mean(list(self._vol_buf)))
            vstd = max(float(np.std(list(self._vol_buf), ddof=1)), VARIANCE_FLOOR)
            feat_5 = np.clip((volume - vmean) / vstd, -3.0, 3.0)
        else:
            feat_5 = 0.0

        self._features = np.array(
            [feat_0, feat_1, feat_2, feat_3, feat_4, feat_5], dtype=np.float64
        )

        # Replace any NaN/Inf with 0
        self._features = np.nan_to_num(self._features, nan=0.0, posinf=0.0, neginf=0.0)

        self._prev_close = close
        return self._features.copy()

    def get_features(self) -> np.ndarray:
        return self._features.copy()


def compute_features_batch(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    session_flags: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Compute features for an entire bar series.
    Returns (n_bars, 6) array.
    """
    n = len(closes)
    engine = FeatureEngine()
    features = np.zeros((n, N_FEATURES))

    for i in range(n):
        sess_reset = bool(session_flags[i]) if session_flags is not None else False
        features[i] = engine.update(
            opens[i], highs[i], lows[i], closes[i], volumes[i], sess_reset
        )

    return features
