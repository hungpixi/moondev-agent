"""
🚀 MoonDev AI Trading Agent — Config
Fork từ CurvedLightGroup/MoonDev-Trading-Ai-Agents
Tối ưu: Forex/XAU | Prop Firm | Ichimoku | MQL5 Export
"""

# ====================================================
# 📊 Instruments (Forex / XAU / Crypto)
# ====================================================
INSTRUMENTS = [
    "XAUUSD",   # 🥇 Gold — instrument chính
    "BTCUSD",   # ₿ Bitcoin
    "EURUSD",   # 💶 EUR/USD
    "GBPUSD",   # 💷 GBP/USD
]
PRIMARY_INSTRUMENT = "XAUUSD"

# ====================================================
# 💰 Account & Risk Management (Prop Firm Style)
# ====================================================
ACCOUNT_BALANCE    = 500      # USD — size tài khoản
LEVERAGE           = 200      # 200x
MONTHLY_TARGET_PCT = 100      # Mục tiêu lợi nhuận: 100%/tháng

# Prop Firm Hard Limits
PROP_FIRM_MODE     = True
MAX_DRAWDOWN_PCT   = 5.0      # Tối đa 5% tổng DD
DAILY_LOSS_LIMIT_PCT = 2.0   # Tối đa 2% loss/ngày
MAX_POSITION_PCT   = 10.0    # Tối đa 10% equity/lệnh

# ====================================================
# 🧮 Composite Scoring System (MQL5 Optimization style)
# Scoring: Balance > PF > RF > MaxDD
# ====================================================
SCORE_WEIGHTS = {
    "return_pct":       0.40,   # Return [%] — quan trọng nhất
    "profit_factor":    0.30,   # Profit Factor
    "recovery_factor":  0.20,   # Recovery Factor
    "max_drawdown":    -0.10,   # MaxDD — âm vì càng thấp càng tốt
}

# Ngưỡng pass/fail (filters trước khi score)
MIN_PROFIT_FACTOR  = 1.5
MIN_RECOVERY_FACTOR = 1.0
MAX_ALLOWED_DD_PCT = 20.0

# ====================================================
# 🕯️ Ichimoku Default Parameters
# ====================================================
ICHI_TENKAN   = 9
ICHI_KIJUN    = 26
ICHI_SENKOU_B = 52
ICHI_DISPLACEMENT = 26

# EMA Filter (trend direction)
EMA_FAST_PERIOD = 50
EMA_SLOW_PERIOD = 200

# ====================================================
# 📈 Data & Timeframes
# ====================================================
TIMEFRAMES = ["15m", "1H", "4H"]
PRIMARY_TF  = "1H"
DATA_PERIOD_DAYS = 365      # 1 year of data

# Walk-forward validation
OPTIMIZE_START = "2025-10-01"   # Q4 2025 — optimize
OPTIMIZE_END   = "2025-12-31"
VALIDATE_START = "2026-01-01"   # Q1 2026 — validate
VALIDATE_END   = "2026-03-10"

# ====================================================
# 🤖 AI Model Settings (v3: Dùng Antigravity trực tiếp)
# ====================================================
# v3 không cần API keys — Antigravity viết code strực tiếp
# Nếu muốn mở lại API mode, uncomment các dòng dưới:
# RESEARCH_MODEL     = "deepseek-chat"
# BACKTEST_MODEL     = "deepseek-chat"
# GEMINI_FALLBACK_MODEL = "gemini-1.5-flash"
# USE_GEMINI_FALLBACK   = True
# AI_TEMPERATURE  = 0.7
# AI_MAX_TOKENS   = 8192

# ====================================================
# 💤 Timing
# ====================================================
SLEEP_BETWEEN_RUNS_MINUTES = 15

# ====================================================
# Legacy Solana config — giữ nguyên nếu muốn dùng
# lại các agent Crypto (trading_agent, whale_agent...)
# ====================================================
# USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# SOL_ADDRESS  = "So11111111111111111111111111111111111111111"
