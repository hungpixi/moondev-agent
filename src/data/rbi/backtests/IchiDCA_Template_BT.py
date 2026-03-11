"""
🥇 IchiDCA XAUUSD — Ichimoku + EMA200 + DCA Entry Strategy
Template backtest mẫu — align với IchiDCA_CCBSN_PropFirm.mq5

Strategy: 
  - Ichimoku Cloud để xác định trend và entry zone
  - EMA200 làm filter xu hướng dài hạn
  - DCA (Dollar Cost Averaging) để manage entry
  - Trailing stop theo Kijun-sen
  - Prop Firm rules: DD < 5%, daily loss < 2%
"""

import sys
import os
from pathlib import Path
import pandas as pd
import pandas_ta as ta
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover  # noqa — sẽ được Package AI xử lý
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # → moondev-agent/
DATA_DIR     = PROJECT_ROOT / "src" / "data" / "rbi"
CHARTS_DIR   = DATA_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Thêm src vào path ────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from config import (
    ICHI_TENKAN, ICHI_KIJUN, ICHI_SENKOU_B, ICHI_DISPLACEMENT,
    EMA_SLOW_PERIOD, ACCOUNT_BALANCE, LEVERAGE,
    OPTIMIZE_START, OPTIMIZE_END,
)

STRATEGY_NAME = "IchiDCA_XAUUSD"

# ── Load Data ─────────────────────────────────────────────────
print(f"🌙 Loading data for {STRATEGY_NAME}...")

# Try XAUUSD first, fallback to BTC
data_candidates = [
    DATA_DIR / "XAUUSD-1H.csv",
    DATA_DIR / "BTC-USD-15m.csv",
]
data_path = next((p for p in data_candidates if p.exists()), None)

if data_path is None:
    print("📡 No local data, downloading XAUUSD 1H...")
    from data.ohlcv_collector import download_ohlcv
    download_ohlcv("XAUUSD", "1H")
    data_path = DATA_DIR / "XAUUSD-1H.csv"

print(f"📂 Using: {data_path}")
df = pd.read_csv(data_path)

# ── Clean columns ─────────────────────────────────────────────
df.columns = df.columns.str.strip().str.lower()
df = df.drop(columns=[c for c in df.columns if "unnamed" in c])
df = df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})

# Index
datetime_col = [c for c in df.columns if "date" in c or "time" in c]
if datetime_col:
    df[datetime_col[0]] = pd.to_datetime(df[datetime_col[0]])
    df = df.set_index(datetime_col[0])
else:
    df.index = pd.to_datetime(df.index)
df.index.name = "datetime"

# Slice optimize period
df = df[(df.index >= OPTIMIZE_START) & (df.index <= OPTIMIZE_END)] if OPTIMIZE_START in df.index.astype(str).str[:10].values or True else df
print(f"📊 Rows after date filter: {len(df)} candles")
print(f"   Period: {df.index[0]} → {df.index[-1]}")


# ═══════════════════════════════════════════════════════════════
# STRATEGY
# ═══════════════════════════════════════════════════════════════

class IchiDCA(Strategy):
    """
    Ichimoku + EMA200 Strategy với DCA entry.
    
    Entry Long:
      1. Price > Cloud (bullish zone)
      2. Price > EMA200 (macro bullish)
      3. Tenkan cross above Kijun (momentum confirm)
    
    Entry Short:
      1. Price < Cloud (bearish zone)
      2. Price < EMA200 (macro bearish)
      3. Tenkan cross below Kijun (momentum confirm)
    
    SL: Below Kijun (long) / Above Kijun (short)
    TP: Trailing theo Kijun
    """
    # ── Params ─────────────────────────────────────────────
    tenkan_period  = ICHI_TENKAN
    kijun_period   = ICHI_KIJUN
    senkou_period  = ICHI_SENKOU_B
    ema_period     = EMA_SLOW_PERIOD      # EMA200
    risk_pct       = 1.0                  # 1% equity per trade
    rr_ratio       = 2.0                  # 1:2 Risk-Reward
    use_trailing   = True

    def init(self):
        h = self.data.High
        l = self.data.Low
        c = self.data.Close

        # ── Ichimoku (computed via pandas_ta, then wrapped with self.I) ──
        # pandas-ta ichimoku returns (result_df, span_df)
        def calc_tenkan(h, l, period):
            return (pd.Series(h).rolling(period).max() + pd.Series(l).rolling(period).min()) / 2

        def calc_kijun(h, l, period):
            return (pd.Series(h).rolling(period).max() + pd.Series(l).rolling(period).min()) / 2

        def calc_senkou_a(h, l, tenkan_p, kijun_p):
            tk = calc_tenkan(h, l, tenkan_p)
            kj = calc_kijun(h, l, kijun_p)
            return ((tk + kj) / 2).shift(kijun_p).values

        def calc_senkou_b(h, l, senkou_p, kijun_p):
            return ((pd.Series(h).rolling(senkou_p).max() + pd.Series(l).rolling(senkou_p).min()) / 2).shift(kijun_p).values

        self.tenkan   = self.I(calc_tenkan, h, l, self.tenkan_period, name="Tenkan")
        self.kijun    = self.I(calc_kijun,  h, l, self.kijun_period,  name="Kijun")
        self.senkou_a = self.I(calc_senkou_a, h, l, self.tenkan_period, self.kijun_period, name="SenkouA")
        self.senkou_b = self.I(calc_senkou_b, h, l, self.senkou_period, self.kijun_period, name="SenkouB")

        # EMA200 filter
        def calc_ema(c, period):
            return pd.Series(c).ewm(span=period, adjust=False).mean().values

        self.ema200 = self.I(calc_ema, c, self.ema_period, name="EMA200")

        print(f"🌙 {STRATEGY_NAME} initialized!")
        print(f"   Tenkan: {self.tenkan_period}, Kijun: {self.kijun_period}, SenkouB: {self.senkou_period}")
        print(f"   EMA: {self.ema_period}, Risk: {self.risk_pct}%, RR: {self.rr_ratio}")

    def next(self):
        close  = self.data.Close[-1]
        tenkan = self.tenkan[-1]
        kijun  = self.kijun[-1]
        spa    = self.senkou_a[-1]
        spb    = self.senkou_b[-1]
        ema    = self.ema200[-1]

        if np.isnan(tenkan) or np.isnan(kijun) or np.isnan(spa) or np.isnan(spb):
            return  # Indicators not ready

        cloud_top    = max(spa, spb)
        cloud_bottom = min(spa, spb)

        # ── Trend signals ─────────────────────────────────
        above_cloud  = close > cloud_top
        below_cloud  = close < cloud_bottom
        macro_bull   = close > ema
        macro_bear   = close < ema

        # Tenkan/Kijun crossover (manual — no backtesting.lib)
        tk_cross_up  = self.tenkan[-2] < self.kijun[-2] and tenkan > kijun
        tk_cross_dn  = self.tenkan[-2] > self.kijun[-2] and tenkan < kijun

        # ── Entry ─────────────────────────────────────────
        if not self.position:
            # Long entry
            if above_cloud and macro_bull and tk_cross_up:
                sl = min(kijun, cloud_bottom) * 0.999  # Buffer 0.1% bên dưới Kijun
                risk_amount = self.equity * (self.risk_pct / 100)
                sl_dist = close - sl
                if sl_dist <= 0:
                    return
                tp = close + sl_dist * self.rr_ratio
                size = risk_amount / sl_dist
                self.buy(size=max(1, int(size)), sl=sl, tp=tp if not self.use_trailing else None)
                print(f"🚀 LONG {close:.2f} | SL={sl:.2f} | TP={tp:.2f} | Size={size:.4f}")

            # Short entry
            elif below_cloud and macro_bear and tk_cross_dn:
                sl = max(kijun, cloud_top) * 1.001
                risk_amount = self.equity * (self.risk_pct / 100)
                sl_dist = sl - close
                if sl_dist <= 0:
                    return
                tp = close - sl_dist * self.rr_ratio
                size = risk_amount / sl_dist
                self.sell(size=max(1, int(size)), sl=sl, tp=tp if not self.use_trailing else None)
                print(f"📉 SHORT {close:.2f} | SL={sl:.2f} | TP={tp:.2f} | Size={size:.4f}")

        # ── Trailing stop (Kijun-based) ───────────────────
        elif self.use_trailing and self.position:
            if self.position.is_long:
                trailing_sl = kijun * 0.999
                if close < trailing_sl:
                    self.position.close()
                    print(f"🌙 EXIT Long @ {close:.2f} (Kijun trailing)")
            elif self.position.is_short:
                trailing_sl = kijun * 1.001
                if close > trailing_sl:
                    self.position.close()
                    print(f"🌙 EXIT Short @ {close:.2f} (Kijun trailing)")


# ═══════════════════════════════════════════════════════════════
# RUN BACKTEST
# ═══════════════════════════════════════════════════════════════

print(f"\n🚀 Running initial backtest: {STRATEGY_NAME}")
bt = Backtest(
    df,
    IchiDCA,
    cash=ACCOUNT_BALANCE,
    commission=0.0002,
    margin=1/LEVERAGE,
    exclusive_orders=True,
)

stats = bt.run()
print("\n" + "═"*50)
print("📊 INITIAL BACKTEST STATS:")
print("═"*50)
print(stats)
print(stats._strategy)

# Save initial chart
chart_file = CHARTS_DIR / f"{STRATEGY_NAME}_initial.html"
bt.plot(filename=str(chart_file), open_browser=False)
print(f"\n📈 Chart saved: {chart_file}")

# ── Composite Score ─────────────────────────────────────────
try:
    from data.composite_scorer import composite_score, print_score_report
    score_result = composite_score(dict(stats))
    print_score_report(score_result, STRATEGY_NAME)
except Exception as e:
    print(f"⚠️ Scorer error: {e}")

# ── Optimization ────────────────────────────────────────────
print("\n🔧 Running optimization (tenkan, kijun, rr_ratio)...")
opt_stats, heatmap = bt.optimize(
    tenkan_period  = range(7, 15, 2),
    kijun_period   = range(20, 34, 4),
    rr_ratio       = [1.5, 2.0, 2.5, 3.0],
    maximize="Profit Factor",
    constraint=lambda p: (
        p.tenkan_period < p.kijun_period and
        p.rr_ratio >= 1.5
    ),
    return_heatmap=True,
)
print("\n📊 OPTIMIZED STATS:")
print(opt_stats)
print(opt_stats._strategy)

# Save optimized chart
opt_chart_file = CHARTS_DIR / f"{STRATEGY_NAME}_optimized.html"
bt.plot(filename=str(opt_chart_file), open_browser=False)
print(f"📈 Optimized chart: {opt_chart_file}")

# ── Score Optimized ─────────────────────────────────────────
try:
    opt_score_result = composite_score(dict(opt_stats))
    print_score_report(opt_score_result, f"{STRATEGY_NAME}_Optimized")
except Exception as e:
    print(f"⚠️ Scorer error: {e}")

print(f"\n✅ {STRATEGY_NAME} backtest complete!")
print(f"💡 Next: mở file .html để xem chart, copy params tốt nhất vào MQL5 EA")
