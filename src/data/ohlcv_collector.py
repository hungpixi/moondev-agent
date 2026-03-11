"""
📥 OHLCV Data Collector — yfinance based
Tải dữ liệu cho XAUUSD, BTCUSD, FX pairs từ Yahoo Finance
Thay thế CSV hardcode của repo gốc.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from termcolor import cprint

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from config import INSTRUMENTS, PRIMARY_TF, DATA_PERIOD_DAYS

# Data directory
DATA_DIR = PROJECT_ROOT / "src" / "data" / "rbi"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Mapping tên instrument sang Yahoo Finance symbol
YFINANCE_SYMBOLS = {
    "XAUUSD": "GC=F",       # Gold Futures
    "BTCUSD": "BTC-USD",    # Bitcoin vs USD
    "EURUSD": "EURUSD=X",   # EUR/USD
    "GBPUSD": "GBPUSD=X",   # GBP/USD
    "USDJPY": "USDJPY=X",
}

# Mapping timeframe sang yfinance interval
TF_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1H":  "1h",
    "4H":  "4h",
    "1D":  "1d",
}


def download_ohlcv(instrument: str, timeframe: str = "1H",
                   days: int = DATA_PERIOD_DAYS,
                   force_refresh: bool = False) -> pd.DataFrame | None:
    """
    Tải OHLCV data từ yfinance.
    
    Args:
        instrument: "XAUUSD", "BTCUSD", "EURUSD", ...
        timeframe:  "15m", "1H", "4H", "1D"
        days:       số ngày lịch sử
        force_refresh: bỏ qua cache nếu True
    
    Returns:
        DataFrame với columns: Open, High, Low, Close, Volume
        None nếu lỗi
    """
    yf_symbol = YFINANCE_SYMBOLS.get(instrument, instrument)
    yf_interval = TF_MAP.get(timeframe, "1h")
    
    # Cache path
    cache_file = DATA_DIR / f"{instrument}-{timeframe}.csv"
    
    # Dùng cache nếu có và không force refresh
    if cache_file.exists() and not force_refresh:
        cprint(f"📂 Loading cached data: {cache_file.name}", "cyan")
        df = pd.read_csv(cache_file, index_col="datetime", parse_dates=True)
        cprint(f"✅ Loaded {len(df)} rows from cache", "green")
        return df
    
    cprint(f"📡 Downloading {instrument} ({yf_interval}, {days}d) from Yahoo Finance...", "yellow")
    
    # yfinance giới hạn intraday data: 15m max 60 ngày, 1h max 730 ngày
    end = datetime.now()
    if yf_interval in ["1m", "5m", "15m", "30m"]:
        days = min(days, 60)
    elif yf_interval in ["1h", "4h"]:
        days = min(days, 730)
    
    start = end - timedelta(days=days)
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=yf_interval,
            auto_adjust=True
        )
        
        if df.empty:
            cprint(f"❌ No data returned for {instrument} ({yf_symbol})", "red")
            return None
        
        # Standardize columns
        df = df.rename(columns=str.title)  # Open, High, Low, Close, Volume
        df.index.name = "datetime"
        
        # Loại bỏ cột thừa
        keep_cols = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in keep_cols if c in df.columns]]
        
        # Loại bỏ NaN
        df = df.dropna(subset=["Close"])
        
        cprint(f"✅ Downloaded {len(df)} candles for {instrument}", "green")
        cprint(f"   Period: {df.index[0].date()} → {df.index[-1].date()}", "cyan")
        
        # Lưu cache
        df.to_csv(cache_file)
        cprint(f"💾 Saved to {cache_file}", "cyan")
        
        return df
        
    except Exception as e:
        cprint(f"❌ Download error for {instrument}: {e}", "red")
        return None


def get_data_for_backtest(instrument: str = "XAUUSD",
                          timeframe: str = "1H",
                          start_date: str | None = None,
                          end_date: str | None = None) -> pd.DataFrame | None:
    """
    Lấy data đã slice theo khoảng thời gian cụ thể (cho walk-forward validation).
    
    Args:
        instrument: instrument code
        timeframe:  khung thời gian
        start_date: "YYYY-MM-DD" — None thì lấy toàn bộ
        end_date:   "YYYY-MM-DD" — None thì đến ngày hôm nay
    
    Returns:
        DataFrame đã slice, sẵn sàng feed vào backtesting.py
    """
    df = download_ohlcv(instrument, timeframe)
    if df is None:
        return None
    
    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]
        
    if df.empty:
        cprint(f"⚠️ No data in range {start_date} → {end_date}", "yellow")
        return None
    
    cprint(f"📊 Backtest data: {len(df)} candles ({start_date} → {end_date})", "cyan")
    return df


def download_all_instruments():
    """Tải tất cả instruments trong config."""
    cprint("🌙 Downloading all instruments...", "magenta")
    for instrument in INSTRUMENTS:
        for tf in ["1H", "4H"]:
            download_ohlcv(instrument, tf)
    cprint("🚀 All downloads complete!", "green")


if __name__ == "__main__":
    # Quick test
    df = download_ohlcv("XAUUSD", "1H", days=30)
    if df is not None:
        print(df.tail())
        print(f"\nShape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")