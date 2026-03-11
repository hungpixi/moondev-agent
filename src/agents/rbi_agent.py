"""
🌙 MoonDev RBI Agent v3 — Antigravity Edition
Fork: CurvedLightGroup/MoonDev-Trading-Ai-Agents

Cải tiến so với v2 (API-based):
  ✅ Giữ nguyên TOÀN BỘ prompts, rules, pipeline logic
  ✅ Không cần API key — Antigravity trực tiếp làm AI
  ✅ Mode 1: Antigravity Mode — in prompt sẵn, paste vào chat
  ✅ Mode 2: API Mode — giữ lại nếu muốn dùng DeepSeek/Gemini
  ✅ Runner: chạy backtest .py file và hiển thị composite score
  ✅ Windows paths, pandas-ta, yfinance

Flow Antigravity Mode:
  Input → [Prep] Extract content → [Print] Prompt cho từng bước
  → Paste vào Antigravity → Copy output → Lưu file → Chạy backtest
"""

import os
import sys
import re
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from io import BytesIO
import requests
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
from termcolor import cprint

# ── Project paths ───────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent        # → src/
DATA_DIR     = PROJECT_ROOT / "data" / "rbi"
RESEARCH_DIR = DATA_DIR / "research"
BACKTEST_DIR = DATA_DIR / "backtests"
PACKAGE_DIR  = DATA_DIR / "backtests_package"
FINAL_DIR    = DATA_DIR / "backtests_final"
MQL5_DIR     = DATA_DIR / "mql5_exports"
CHARTS_DIR   = DATA_DIR / "charts"

for d in [DATA_DIR, RESEARCH_DIR, BACKTEST_DIR, PACKAGE_DIR, FINAL_DIR, MQL5_DIR, CHARTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from config import (
    ACCOUNT_BALANCE, LEVERAGE,
    OPTIMIZE_START, OPTIMIZE_END, VALIDATE_START, VALIDATE_END,
    ICHI_TENKAN, ICHI_KIJUN, ICHI_SENKOU_B,
    EMA_SLOW_PERIOD, MAX_DRAWDOWN_PCT, DAILY_LOSS_LIMIT_PCT,
)

DEFAULT_DATA_PATH = DATA_DIR / "BTC-USD-15m.csv"

# ═══════════════════════════════════════════════════════════════
# PROMPTS — Giữ nguyên toàn bộ rules Ichimoku + MQL5
# ═══════════════════════════════════════════════════════════════

RESEARCH_PROMPT = f"""
Bạn là Research AI của hệ thống MoonDev Trading — chuyên phân tích chiến lược theo tinh thần Prop Firm & MQL5 backtest.

NAMING RULES:
1. Tạo tên UNIQUE 2 từ (PascalCase) cho strategy này
2. Từ 1: phương pháp chính (Ichi, EMA, MACD, Momentum, DCA...)
3. Từ 2: kỹ thuật đặc trưng (Cloud, Cross, Divergence, Breakout...)
4. Ví dụ tốt: "IchiCloud", "EMAFusion", "MomentumBreak", "DualKijun"

Output format bắt buộc:
STRATEGY_NAME: [TwoWordName]

STRATEGY_DETAILS:
[Phân tích chi tiết]

Phân tích tập trung vào:
1. **Indicator chính** (ưu tiên Ichimoku: nêu rõ Tenkan={ICHI_TENKAN}, Kijun={ICHI_KIJUN}, Senkou B={ICHI_SENKOU_B})
2. **Filter xu hướng** (EMA{EMA_SLOW_PERIOD} H4 — price trên/dưới EMA → bias)
3. **Điều kiện vào lệnh** (cụ thể: cross, cloud breakout, price action)
4. **Điều kiện thoát lệnh** (SL: dưới Kijun/cloud; TP: RR ratio hoặc trailing)
5. **Prop Firm compatibility** (DD < {MAX_DRAWDOWN_PCT}%, daily loss < {DAILY_LOSS_LIMIT_PCT}%)
6. **Timeframe** (H1 entry, H4 trend)
7. **Risk management** (position sizing theo % equity, không over-leverage)
"""

BACKTEST_PROMPT = f"""
Bạn là Backtest AI — code chiến lược trading bằng backtesting.py framework (Python).

QUAN TRỌNG — WINDOWS PATHS:
- Đừng hardcode path macOS /Users/md/...
- Dùng pathlib.Path(__file__).parent để tìm data dynamically
- Thay tất cả backtesting.lib.crossover bằng array index comparison

PANDAS-TA (không dùng TA-Lib):
- import pandas_ta as ta
- Ví dụ: df.ta.ema(length=200) → trả về Series

ICHIMOKU — Tính ĐÚNG bằng pandas-ta:
```python
import pandas_ta as ta
ichi_result = ta.ichimoku(high, low, close,
                          tenkan={ICHI_TENKAN}, kijun={ICHI_KIJUN}, senkou={ICHI_SENKOU_B})
ichi = ichi_result[0]  # Main DataFrame
# Columns: ISA_9 (SpanA), ISB_26 (SpanB), ITS_9 (Tenkan), IKS_26 (Kijun), ICS_26 (Chikou)
```

ACCOUNT CONFIG (align với Prop Firm):
- cash = {ACCOUNT_BALANCE}          # ${ACCOUNT_BALANCE} tài khoản
- commission = 0.0002               # ~0.02% spread
- margin = 1/{LEVERAGE}              # leverage {LEVERAGE}x
- exclusive_orders = True

BACKTEST EXECUTION ORDER bắt buộc:
1. Load data (pathlib dynamic path)
2. Strategy class với self.I() wrapper cho MỌI indicator
3. Run initial backtest → print full stats
4. Lưu chart HTML (open_browser=False)
5. Run optimization (3-5 params)
6. Print optimized stats + chart

SAU KHI CHẠY XONG — tính COMPOSITE SCORE (bắt buộc):
```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.composite_scorer import composite_score, print_score_report
score_result = composite_score(dict(stats))
print_score_report(score_result, strategy_name)
```

WALK-FORWARD:
- Optimize: {OPTIMIZE_START} → {OPTIMIZE_END}
- Validate: {VALIDATE_START} → {VALIDATE_END}

CROSSOVER (không dùng backtesting.lib):
- Bullish cross: series_a[-2] < series_b[-2] and series_a[-1] > series_b[-1]
- Bearish cross: series_a[-2] > series_b[-2] and series_a[-1] < series_b[-1]

Debug prints phải có emoji 🌙✨🚀 để dễ theo dõi.
"""

DEBUG_PROMPT = """
Bạn là Debug AI — sửa lỗi kỹ thuật mà KHÔNG thay đổi logic chiến lược.

Fix các lỗi:
1. Syntax errors
2. Import statements (đảm bảo pandas_ta thay TA-Lib)
3. Path issues (Windows vs macOS)
4. backtesting.lib.crossover → array indexing
5. Variable scope, naming
6. pandas-ta Ichimoku column names (ISA_9, ISB_26, ITS_9, IKS_26, ICS_26)
7. self.I() wrapper cho tất cả indicators

KHÔNG thay đổi:
- Strategy logic, Entry/exit conditions
- Risk management rules, Parameter values

Trả về complete fixed code.
"""

PACKAGE_PROMPT = """
Bạn là Package AI — đảm bảo code KHÔNG dùng bất kỳ backtesting.lib nào.

❌ CẤM TUYỆT ĐỐI:
- from backtesting.lib import *
- from backtesting.lib import crossover
- backtesting.lib.crossover(a, b)

✅ THAY THẾ BẮT BUỘC:
- Crossover bullish: a[-2] < b[-2] and a[-1] > b[-1]
- Crossover bearish: a[-2] > b[-2] and a[-1] < b[-1]
- Indicators: dùng pandas_ta (không phải TA-Lib hay backtesting.lib)

Scan toàn bộ code, fix hết, trả về complete code.
"""

EXPORT_MQL5_PROMPT = f"""
Bạn là MQL5 Export AI — chuyển đổi chiến lược Python đã backtest thành MQL5 Expert Advisor skeleton.

OUTPUT: File MQL5 (.mq5) bao gồm:

1. **Header & Properties**
   - #property copyright, version, description
   - #include <Trade/Trade.mqh>

2. **Input Parameters** (align với params đã optimize):
   - InpTenkan, InpKijun, InpSenkouB (Ichimoku)
   - InpEMAFast, InpEMASlow
   - InpRiskPct (% equity per trade)
   - InpTPRR (Risk-Reward ratio)
   - InpMaxDD_Pct = {MAX_DRAWDOWN_PCT}
   - InpDailyLoss_Pct = {DAILY_LOSS_LIMIT_PCT}

3. **Global Variables**: CTrade trade object, indicator handles

4. **OnInit()**: Initialize indicator handles, validate params

5. **OnTick()**:
   - check_prop_firm_limits() → return nếu vi phạm DD
   - get_indicators() → lấy giá trị mới nhất
   - signal = get_signal() → BUY/SELL/NONE
   - Nếu có signal và không có position: open_trade(signal)
   - Trailing stop logic nếu có position

6. **Signal functions**: is_above_cloud(), tenkan_kijun_cross_up(), ema_filter_bullish()...

7. **Risk Management**: calculate_lot_size(), check_daily_loss_limit(), check_max_drawdown()

8. **Comments** đầy đủ bằng tiếng Việt.

QUAN TRỌNG:
- Dùng iIchimoku() built-in của MT5
- Code phải compile được trong MetaEditor
- Comment: // Generated by MoonDev AI Agent — Comarai.com
"""

# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_input_content(user_input: str) -> str:
    """Xử lý input: text, YouTube URL, PDF URL hoặc file path."""
    # YouTube
    yt_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", user_input)
    if yt_match:
        vid_id = yt_match.group(1)
        cprint(f"📺 Downloading YouTube transcript: {vid_id}", "yellow")
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(vid_id)
            try:
                t = transcript_list.find_generated_transcript(["en"])
            except Exception:
                t = list(transcript_list)[0]
            segments = t.fetch()
            text = " ".join(s["text"] for s in segments)
            cprint(f"✅ Transcript: {len(text)} chars", "green")
            return text
        except Exception as e:
            cprint(f"❌ YouTube error: {e}", "red")
            return user_input

    # URL PDF
    if user_input.startswith("http") and ".pdf" in user_input:
        cprint("📄 Downloading PDF...", "yellow")
        try:
            r = requests.get(user_input, timeout=15)
            reader = PyPDF2.PdfReader(BytesIO(r.content))
            text = " ".join(page.extract_text() or "" for page in reader.pages)
            cprint(f"✅ PDF: {len(text)} chars", "green")
            return text
        except Exception as e:
            cprint(f"❌ PDF error: {e}", "red")
            return user_input

    # Local PDF
    if user_input.endswith(".pdf") and Path(user_input).exists():
        try:
            with open(user_input, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = " ".join(page.extract_text() or "" for page in reader.pages)
            return text
        except Exception as e:
            cprint(f"❌ Local PDF error: {e}", "red")

    return user_input


def extract_code(text: str) -> str:
    """Extract Python code từ markdown code blocks."""
    code_match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    if "import " in text or "class " in text or "def " in text:
        return text.strip()
    return text.strip()


def extract_mql5_code(text: str) -> str:
    """Extract MQL5 code từ markdown."""
    code_match = re.search(r"```(?:mq5|cpp|c\+\+)?\n(.*?)```", text, re.DOTALL)
    return code_match.group(1).strip() if code_match else text.strip()


def extract_strategy_name(text: str) -> str:
    """Extract strategy name từ output Research AI."""
    match = re.search(r"STRATEGY_NAME:\s*([A-Za-z0-9_]+)", text)
    if match:
        return match.group(1).strip()
    return f"Strategy_{datetime.now().strftime('%m%d_%H%M')}"


def save_file(content: str, directory: Path, name: str, ext: str = "py") -> Path:
    """Lưu file và trả về path."""
    ts = datetime.now().strftime("%m%d_%H%M")
    filepath = directory / f"{name}_{ts}.{ext}"
    filepath.write_text(content, encoding="utf-8")
    cprint(f"💾 Saved: {filepath}", "cyan")
    return filepath


def run_backtest_file(filepath: Path) -> bool:
    """Chạy file backtest, hiển thị output + composite score."""
    if not filepath.exists():
        cprint(f"❌ Không tìm thấy: {filepath}", "red")
        return False
    cprint(f"\n🚀 Chạy: {filepath.name}", "cyan", attrs=["bold"])
    cprint("─" * 50, "cyan")
    result = subprocess.run([sys.executable, str(filepath)])
    success = result.returncode == 0
    if success:
        cprint(f"\n✅ Hoàn tất: {filepath.name}", "green", attrs=["bold"])
    else:
        cprint(f"\n❌ Lỗi (exit {result.returncode}) — paste lỗi vào Antigravity để debug!", "red")
    return success


# ═══════════════════════════════════════════════════════════════
# ANTIGRAVITY MODE — In prompt sẵn để paste vào chat
# ═══════════════════════════════════════════════════════════════

DIVIDER = "─" * 70

def print_step_prompt(step: int, total: int, role: str, system_prompt: str, user_content: str):
    """In prompt của từng step theo format dễ copy-paste."""
    cprint(f"\n{'═'*70}", "magenta")
    cprint(f"  🌙 STEP [{step}/{total}] — {role}", "magenta", attrs=["bold"])
    cprint(f"{'═'*70}", "magenta")
    cprint("\n📋 SYSTEM PROMPT (đã built-in, Antigravity đọc context này):", "yellow")
    print(system_prompt[:800] + "..." if len(system_prompt) > 800 else system_prompt)
    cprint(f"\n{DIVIDER}", "cyan")
    cprint("💬 NỘI DUNG GỬI CHO ANTIGRAVITY:", "yellow", attrs=["bold"])
    cprint(f"{DIVIDER}", "cyan")
    print(user_content[:3000] + "\n[...truncated, xem file để đọc đầy đủ...]"
          if len(user_content) > 3000 else user_content)
    cprint(f"\n{DIVIDER}", "cyan")


def antigravity_pipeline(strategy_input: str):
    """
    Pipeline Antigravity Mode — in từng bước để paste vào chat.
    Antigravity (AI trong chat) làm phần research + code.
    """
    cprint("\n" + "═"*70, "magenta")
    cprint("  🌙 MoonDev RBI — ANTIGRAVITY MODE", "magenta", attrs=["bold"])
    cprint("  AI trong chat này SẼ làm việc, không cần API key!", "cyan")
    cprint("═"*70 + "\n", "magenta")

    # ── Chuẩn bị nội dung input ────────────────────────────
    cprint("⏳ Đang xử lý input...", "yellow")
    content = get_input_content(strategy_input)
    content_preview = content[:500] + "..." if len(content) > 500 else content
    cprint(f"✅ Input ready: {len(content)} chars", "green")

    # Detect data path
    xau_path = DATA_DIR / "XAUUSD-1H.csv"
    data_path = xau_path if xau_path.exists() else DEFAULT_DATA_PATH

    # ── [1] Research ────────────────────────────────────────
    print_step_prompt(
        step=1, total=5, role="Research AI",
        system_prompt=RESEARCH_PROMPT,
        user_content=f"""Phân tích chiến lược trading sau và trả về theo format bắt buộc:

{content}

Nhớ:
- Bắt đầu bằng: STRATEGY_NAME: [TwoWordName]
- Tiếp theo: STRATEGY_DETAILS: [Chi tiết đầy đủ]
"""
    )
    cprint("⏸️  PASTE prompt trên vào Antigravity, sau đó nhập output vào đây:", "yellow", attrs=["bold"])
    research_output = ""
    print("(Nhập output, kết thúc bằng dòng trống + 'END' rồi Enter)")
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        research_output += line + "\n"

    if not research_output.strip():
        cprint("❌ Không có output. Thoát.", "red")
        return

    strategy_name = extract_strategy_name(research_output)
    cprint(f"✅ Strategy name: {strategy_name}", "green", attrs=["bold"])
    research_file = save_file(research_output, RESEARCH_DIR, strategy_name, ext="txt")

    # ── [2] Backtest Code ───────────────────────────────────
    print_step_prompt(
        step=2, total=5, role="Backtest AI",
        system_prompt=BACKTEST_PROMPT,
        user_content=f"""Viết complete backtest code cho strategy sau:

Strategy Name: {strategy_name}
Data path: {data_path}
Charts dir: {CHARTS_DIR}

Research Output:
{research_output}
"""
    )
    cprint("⏸️  PASTE prompt trên vào Antigravity → copy Python code output:", "yellow", attrs=["bold"])
    backtest_lines = []
    print("(Nhập Python code, kết thúc bằng 'END')")
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        backtest_lines.append(line)
    backtest_code = extract_code("\n".join(backtest_lines))
    backtest_file = save_file(backtest_code, BACKTEST_DIR, f"{strategy_name}_BT")

    # ── [3] Debug ───────────────────────────────────────────
    print_step_prompt(
        step=3, total=5, role="Debug AI",
        system_prompt=DEBUG_PROMPT,
        user_content=f"""Fix lỗi kỹ thuật trong code sau (KHÔNG đổi logic):

```python
{backtest_code}
```"""
    )
    cprint("⏸️  PASTE vào Antigravity → nhập code đã fix:", "yellow", attrs=["bold"])
    debug_lines = []
    print("(Nhập fixed code hoặc 'SKIP' nếu không cần fix)")
    while True:
        line = input()
        if line.strip().upper() == "SKIP":
            break
        if line.strip().upper() == "END":
            break
        debug_lines.append(line)
    if debug_lines:
        backtest_code = extract_code("\n".join(debug_lines))

    # ── [4] Package ─────────────────────────────────────────
    print_step_prompt(
        step=4, total=5, role="Package AI",
        system_prompt=PACKAGE_PROMPT,
        user_content=f"""Clean code sau — xóa backtesting.lib nếu có:

```python
{backtest_code}
```"""
    )
    cprint("⏸️  PASTE vào Antigravity → nhập final clean code:", "yellow", attrs=["bold"])
    pkg_lines = []
    print("(Nhập final code hoặc 'SKIP')")
    while True:
        line = input()
        if line.strip().upper() in ("SKIP", "END"):
            break
        pkg_lines.append(line)
    if pkg_lines:
        backtest_code = extract_code("\n".join(pkg_lines))

    save_file(backtest_code, PACKAGE_DIR, f"{strategy_name}_PKG")
    final_file = save_file(backtest_code, FINAL_DIR, f"{strategy_name}_BTFinal")

    # ── [5] MQL5 Export ─────────────────────────────────────
    print_step_prompt(
        step=5, total=5, role="MQL5 Export AI",
        system_prompt=EXPORT_MQL5_PROMPT,
        user_content=f"""Chuyển Python strategy này thành MQL5 EA:

Strategy: {strategy_name}
Research: {research_output[:1000]}

Python Code:
{backtest_code[:2000]}
"""
    )
    cprint("⏸️  PASTE vào Antigravity → nhập .mq5 code:", "yellow", attrs=["bold"])
    mql5_lines = []
    print("(Nhập MQL5 code hoặc 'SKIP')")
    while True:
        line = input()
        if line.strip().upper() in ("SKIP", "END"):
            break
        mql5_lines.append(line)
    if mql5_lines:
        mql5_code = extract_mql5_code("\n".join(mql5_lines))
        save_file(mql5_code, MQL5_DIR, f"{strategy_name}_EA", ext="mq5")

    # ── Summary ─────────────────────────────────────────────
    cprint("\n" + "═"*60, "green")
    cprint(f"  ✅ Pipeline hoàn tất: {strategy_name}", "green", attrs=["bold"])
    cprint(f"  📁 Research:  {RESEARCH_DIR}", "white")
    cprint(f"  📁 Final BT:  {FINAL_DIR}", "white")
    cprint(f"  📁 MQL5 EA:  {MQL5_DIR}", "white")
    cprint("═"*60, "green")
    cprint(f"\n▶️  Chạy backtest: python src/agents/rbi_agent.py --file {strategy_name}_BTFinal", "yellow")
    cprint(   "   Hoặc chạy file trực tiếp để xem composite score!", "cyan")


# ═══════════════════════════════════════════════════════════════
# API MODE (giữ lại, dùng khi muốn)
# ═══════════════════════════════════════════════════════════════

def api_pipeline(strategy_input: str):
    """
    API Mode — gọi DeepSeek/Gemini như v2.
    Uncomment và cài openai + google-generativeai nếu muốn dùng.
    """
    try:
        import openai
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        cprint("❌ API mode cần: pip install openai python-dotenv", "red")
        cprint("💡 Dùng Antigravity Mode (mặc định) để không cần API!", "yellow")
        return

    cprint("⚠️ API Mode — cần DEEPSEEK_KEY hoặc GEMINI_KEY trong .env", "yellow")
    # ... giữ lại vị trí để implement nếu cần sau


# ═══════════════════════════════════════════════════════════════
# RUNNER: Chạy backtest files có sẵn
# ═══════════════════════════════════════════════════════════════

def show_runner_menu():
    """Menu chọn file backtest để chạy."""
    files = sorted(BACKTEST_DIR.glob("*.py")) + sorted(FINAL_DIR.glob("*.py"))
    if not files:
        cprint("📁 Chưa có file backtest. Dùng Antigravity Mode để tạo!", "yellow")
        return

    cprint("\n" + "═"*55, "cyan")
    cprint("  🚀 Runner — Chọn file backtest", "cyan", attrs=["bold"])
    cprint("═"*55, "cyan")
    for i, f in enumerate(files, 1):
        tag = "[FINAL]" if "Final" in f.name or "final" in str(f.parent) else "[BT]   "
        cprint(f"  {i:2}. {tag} {f.name}", "white")
    cprint(f"\n  0. Chạy TẤT CẢ", "yellow")
    cprint("  q. Thoát", "white")
    cprint("─"*55, "cyan")

    choice = input("\n🎯 Chọn: ").strip().lower()
    if choice == "q":
        return
    elif choice == "0":
        for f in files:
            run_backtest_file(f)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                run_backtest_file(files[idx])
        except ValueError:
            cprint("❌ Input không hợp lệ", "red")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="🌙 MoonDev RBI Agent — Antigravity Edition",
    )
    parser.add_argument("--mode",
        choices=["antigravity", "api", "runner"],
        default="antigravity",
        help="antigravity (default) | api | runner"
    )
    parser.add_argument("--input",  help="Strategy text / YouTube URL / PDF path")
    parser.add_argument("--file",   help="Chạy trực tiếp 1 backtest file")
    parser.add_argument("--run-all", action="store_true", help="Chạy tất cả backtests")
    parser.add_argument("--data",   nargs=2, metavar=("INSTRUMENT", "TF"),
                        help="Download data: --data XAUUSD 1H")

    args = parser.parse_args()

    # Download data
    if args.data:
        sys.path.insert(0, str(PROJECT_ROOT / "data"))
        from ohlcv_collector import download_ohlcv
        download_ohlcv(args.data[0], args.data[1])
        sys.exit(0)

    # Chạy file cụ thể
    if args.file:
        candidates = list(BACKTEST_DIR.glob(f"*{args.file}*")) + list(FINAL_DIR.glob(f"*{args.file}*"))
        target = Path(args.file) if Path(args.file).exists() else (candidates[0] if candidates else None)
        if target:
            run_backtest_file(target)
        else:
            cprint(f"❌ Không tìm thấy: {args.file}", "red")
        sys.exit(0)

    # Chạy tất cả
    if args.run_all:
        for f in list(FINAL_DIR.glob("*.py")):
            run_backtest_file(f)
        sys.exit(0)

    # Mode selection
    if args.mode == "antigravity" or not args.mode:
        cprint("\n🌙 MoonDev RBI Agent — Antigravity Mode", "magenta", attrs=["bold"])
        cprint("=" * 55, "magenta")
        cprint("Modes:", "cyan")
        cprint("  1. 🤖 Antigravity Pipeline (step-by-step, paste vào chat)", "white")
        cprint("  2. 🚀 Runner (chạy backtest file có sẵn)", "white")
        cprint("  3. 📥 Download Data (XAUUSD, BTC, FX)", "white")
        cprint("=" * 55, "magenta")
        choice = input("\nChọn (1/2/3): ").strip()

        if choice == "1":
            strategy_input = args.input or input("\n📋 Nhập strategy / YouTube URL / PDF path:\n> ").strip()
            if strategy_input:
                antigravity_pipeline(strategy_input)

        elif choice == "2":
            show_runner_menu()

        elif choice == "3":
            instr = input("Instrument (XAUUSD/BTCUSD/EURUSD): ").strip() or "XAUUSD"
            tf    = input("Timeframe (1H/4H/15m): ").strip() or "1H"
            sys.path.insert(0, str(PROJECT_ROOT / "data"))
            from ohlcv_collector import download_ohlcv
            download_ohlcv(instr, tf)

    elif args.mode == "runner":
        show_runner_menu()

    elif args.mode == "api":
        strategy_input = args.input or input("📋 Nhập strategy / URL:\n> ").strip()
        api_pipeline(strategy_input)
