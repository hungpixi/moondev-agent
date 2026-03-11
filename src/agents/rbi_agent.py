"""
🌙 MoonDev RBI Agent v3 — Antigravity Edition
Fork: CurvedLightGroup/MoonDev-Trading-Ai-Agents

v3 so với v2:
  ✅ Bỏ hoàn toàn API calls (DeepSeek / Gemini) — không cần API key
  ✅ Antigravity trực tiếp viết strategy code trong chat
  ✅ File này chỉ là RUNNER: load data → chạy backtest → score → save
  ✅ Gọn hơn 10x (từ 580 → ~120 dòng)

Cách dùng:
  1. Nói với Antigravity: "viết backtest chiến lược X cho XAUUSD"
  2. Antigravity viết file .py vào src/data/rbi/backtests/
  3. Chạy: python src/agents/rbi_agent.py --file <tên_file>
     hoặc:  python src/agents/rbi_agent.py --run-all
"""

import sys
import re
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from termcolor import cprint

# ── Paths ─────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent       # → src/
DATA_DIR     = PROJECT_ROOT / "data" / "rbi"
BACKTEST_DIR = DATA_DIR / "backtests"
FINAL_DIR    = DATA_DIR / "backtests_final"
MQL5_DIR     = DATA_DIR / "mql5_exports"
CHARTS_DIR   = DATA_DIR / "charts"
RESEARCH_DIR = DATA_DIR / "research"

for d in [BACKTEST_DIR, FINAL_DIR, MQL5_DIR, CHARTS_DIR, RESEARCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config import (không import AI-related stuff) ─────────────
sys.path.insert(0, str(PROJECT_ROOT))
from config import ACCOUNT_BALANCE, LEVERAGE


# ═══════════════════════════════════════════════════════════════
# RUNNER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def run_backtest_file(filepath: Path) -> bool:
    """
    Chạy một file backtest Python và hiển thị output.
    Returns True nếu chạy thành công.
    """
    if not filepath.exists():
        cprint(f"❌ File không tìm thấy: {filepath}", "red")
        return False

    cprint(f"\n🚀 Chạy backtest: {filepath.name}", "cyan", attrs=["bold"])
    cprint("─" * 50, "cyan")

    result = subprocess.run(
        [sys.executable, str(filepath)],
        capture_output=False,   # Show output trực tiếp
        text=True,
    )

    if result.returncode == 0:
        cprint(f"\n✅ {filepath.name} hoàn tất!", "green", attrs=["bold"])
        return True
    else:
        cprint(f"\n❌ {filepath.name} bị lỗi (exit code {result.returncode})", "red")
        cprint("💡 Gửi lỗi cho Antigravity để debug!", "yellow")
        return False


def list_backtest_files() -> list[Path]:
    """Liệt kê tất cả file backtest trong thư mục."""
    files = sorted(BACKTEST_DIR.glob("*.py"))
    if not files:
        cprint("📁 Chưa có file backtest nào.", "yellow")
        cprint("   → Nói với Antigravity để viết strategy đầu tiên!", "cyan")
        return []
    return files


def show_menu():
    """Hiển thị menu tương tác."""
    files = list_backtest_files()
    if not files:
        return

    cprint("\n" + "═" * 55, "magenta")
    cprint("  🌙 MoonDev Runner — Chọn backtest để chạy", "magenta", attrs=["bold"])
    cprint("═" * 55, "magenta")

    for i, f in enumerate(files, 1):
        # Detect instrument từ tên file
        name = f.stem
        cprint(f"  {i:2}. {name}", "white")

    cprint(f"\n  0. Chạy TẤT CẢ ({len(files)} files)", "yellow")
    cprint("  q. Thoát", "white")
    cprint("─" * 55, "magenta")

    choice = input("\n🎯 Chọn (số hoặc q): ").strip().lower()

    if choice == "q":
        return
    elif choice == "0":
        run_all_backtests(files)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                run_backtest_file(files[idx])
            else:
                cprint("❌ Số không hợp lệ", "red")
        except ValueError:
            cprint("❌ Input không hợp lệ", "red")


def run_all_backtests(files: list[Path] | None = None):
    """Chạy tất cả file backtest và tổng kết."""
    if files is None:
        files = list_backtest_files()
    if not files:
        return

    cprint(f"\n🚀 Chạy {len(files)} backtests...", "cyan", attrs=["bold"])
    results = {}

    for f in files:
        success = run_backtest_file(f)
        results[f.name] = "✅ OK" if success else "❌ FAIL"

    # Summary
    cprint("\n" + "═" * 50, "green")
    cprint("  📊 KẾT QUẢ", "green", attrs=["bold"])
    cprint("─" * 50, "green")
    for name, status in results.items():
        cprint(f"  {status}  {name}", "white")
    cprint("═" * 50, "green")


def download_data(instrument: str = "XAUUSD", timeframe: str = "1H"):
    """Download OHLCV data từ yfinance."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "data"))
        from ohlcv_collector import download_ohlcv
        df = download_ohlcv(instrument, timeframe)
        if df is not None:
            cprint(f"✅ Data sẵn sàng: {instrument}-{timeframe}.csv ({len(df)} rows)", "green")
    except Exception as e:
        cprint(f"❌ Download lỗi: {e}", "red")


def show_help():
    """In hướng dẫn sử dụng."""
    cprint("\n" + "═" * 60, "cyan")
    cprint("  🌙 MoonDev RBI Runner — Hướng Dẫn", "cyan", attrs=["bold"])
    cprint("═" * 60, "cyan")
    print("""
  CÁCH DÙNG VỚI ANTIGRAVITY:
  ─────────────────────────────────────────────────────
  1. Mở Antigravity, nói:
     "Viết backtest Ichimoku cho XAUUSD 1H"

  2. Antigravity viết file vào:
     src/data/rbi/backtests/<TênStrategy>_BT.py

  3. Chạy bằng runner này:
     python src/agents/rbi_agent.py              → menu
     python src/agents/rbi_agent.py --list       → liệt kê files
     python src/agents/rbi_agent.py --run-all    → chạy hết
     python src/agents/rbi_agent.py --file IchiDCA_BT.py

  4. Download data (nếu chưa có):
     python src/agents/rbi_agent.py --data XAUUSD 1H

  LUỒNG CHUẨN:
  ─────────────────────────────────────────────────────
  Antigravity viết code → bạn chạy → xem composite score
  → gửi kết quả cho Antigravity → tối ưu → lặp lại
    """)
    cprint("═" * 60, "cyan")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="🌙 MoonDev RBI Runner — Antigravity Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file",     help="Tên file backtest cụ thể (trong thư mục backtests/)")
    parser.add_argument("--run-all",  action="store_true", help="Chạy tất cả file backtest")
    parser.add_argument("--list",     action="store_true", help="Liệt kê các file backtest")
    parser.add_argument("--data",     nargs=2, metavar=("INSTRUMENT", "TIMEFRAME"),
                                      help="Download data: --data XAUUSD 1H")
    parser.add_argument("--help-me",  action="store_true", help="Hướng dẫn sử dụng")

    args = parser.parse_args()

    if args.help_me:
        show_help()

    elif args.list:
        files = list_backtest_files()
        for f in files:
            cprint(f"  📄 {f.name}", "white")

    elif args.data:
        download_data(args.data[0], args.data[1])

    elif args.file:
        # Tìm file (có thể nhập tên không đầy đủ)
        target = BACKTEST_DIR / args.file
        if not target.exists():
            # Thử tìm partial match
            matches = list(BACKTEST_DIR.glob(f"*{args.file}*"))
            if matches:
                target = matches[0]
                cprint(f"📂 Tìm thấy: {target.name}", "cyan")
            else:
                cprint(f"❌ Không tìm thấy file: {args.file}", "red")
                sys.exit(1)
        run_backtest_file(target)

    elif args.run_all:
        run_all_backtests()

    else:
        # Default: interactive menu
        show_menu()
