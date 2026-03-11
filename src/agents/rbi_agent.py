"""
🌙 MoonDev RBI Agent — Nâng Cấp Ichimoku + MQL5 Export
Fork: CurvedLightGroup/MoonDev-Trading-Ai-Agents

Cải tiến so với gốc:
  ✅ Windows-compatible paths (không hardcode macOS)
  ✅ Prompts enforce Ichimoku + EMA filter (phù hợp MQL5 EA)
  ✅ Composite scoring sau mỗi backtest (Balance > PF > RF > MaxDD)
  ✅ Walk-forward validation tự động (Q4 2025 → Q1 2026)
  ✅ Agent thứ 5: MQL5 Export (generate .mq5 skeleton)
  ✅ Gemini API fallback nếu DeepSeek lỗi
  ✅ yfinance data download (XAUUSD, BTCUSD, FX)

Flow: Input → [1] Research AI → [2] Backtest AI → [3] Debug AI
      → [4] Package AI → [5] MQL5 Export AI → Score & Report
"""

import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from io import BytesIO
import requests
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import openai
from termcolor import cprint
import threading
import itertools

# ── Project paths ───────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent.parent          # → src/
DATA_DIR       = PROJECT_ROOT / "data" / "rbi"
RESEARCH_DIR   = DATA_DIR / "research"
BACKTEST_DIR   = DATA_DIR / "backtests"
PACKAGE_DIR    = DATA_DIR / "backtests_package"
FINAL_DIR      = DATA_DIR / "backtests_final"
MQL5_DIR       = DATA_DIR / "mql5_exports"            # MỚI
CHARTS_DIR     = DATA_DIR / "charts"

for d in [DATA_DIR, RESEARCH_DIR, BACKTEST_DIR, PACKAGE_DIR, FINAL_DIR, MQL5_DIR, CHARTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config ──────────────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
from config import (
    RESEARCH_MODEL, BACKTEST_MODEL, DEBUG_MODEL, EXPORT_MQL5_MODEL,
    AI_MAX_TOKENS, AI_TEMPERATURE,
    GEMINI_FALLBACK_MODEL, USE_GEMINI_FALLBACK,
    ACCOUNT_BALANCE, LEVERAGE,
    OPTIMIZE_START, OPTIMIZE_END, VALIDATE_START, VALIDATE_END,
    ICHI_TENKAN, ICHI_KIJUN, ICHI_SENKOU_B, ICHI_DISPLACEMENT,
    EMA_SLOW_PERIOD,
    MAX_DRAWDOWN_PCT, DAILY_LOSS_LIMIT_PCT,
)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ── Data path helper ─────────────────────────────────────────
def get_data_path(instrument: str = "XAUUSD", timeframe: str = "1H") -> Path:
    """Trả về path file CSV, tải nếu chưa có."""
    csv_path = DATA_DIR / f"{instrument}-{timeframe}.csv"
    if not csv_path.exists():
        cprint(f"📡 Data not found locally, downloading {instrument}...", "yellow")
        try:
            from data.ohlcv_collector import download_ohlcv
            download_ohlcv(instrument, timeframe)
        except Exception as e:
            cprint(f"⚠️ Download failed: {e}. Will use BTC-USD-15m.csv fallback.", "yellow")
    return csv_path

DEFAULT_DATA_PATH = DATA_DIR / "BTC-USD-15m.csv"

# ═══════════════════════════════════════════════════════════════
# PROMPTS — Ichimoku-aware, MQL5-aligned
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
# Ichimoku luôn trả về (DataFrame_span_a_b, DataFrame_span_ab_precomputed)
ichi_result = ta.ichimoku(high, low, close,
                          tenkan={ICHI_TENKAN}, kijun={ICHI_KIJUN}, senkou={ICHI_SENKOU_B})
ichi = ichi_result[0]  # Main DataFrame
# Columns: ISA_9 (SpanA), ISB_26 (SpanB), ITS_9 (Tenkan), IKS_26 (Kijun), ICS_26 (Chikou)
```

ACCOUNT CONFIG (align với Prop Firm):
- cash = {ACCOUNT_BALANCE}          # $500 tài khoản
- commission = 0.0002               # ~0.02% spread
- margin = 1/{LEVERAGE}              # leverage {LEVERAGE}x
- exclusive_orders = True           # Không hold nhiều lệnh cùng chiều

BACKTEST EXECUTION ORDER bắt buộc:
1. Load data (dùng pathlib, detect instrument từ strategy name)
2. Implement Strategy class với self.I() wrapper
3. Run initial backtest → print full stats
4. Lưu chart: bt.plot(filename=str(CHARTS_DIR / f"{{strategy_name}}_initial.html"), open_browser=False)  
5. Run optimization (optimize 3-5 params)
6. Print optimized stats + chart

SAU KHI CHẠY XONG — tính COMPOSITE SCORE:
```python
# Thêm vào cuối script
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.composite_scorer import composite_score, print_score_report

stats_dict = dict(stats)
score_result = composite_score(stats_dict)
print_score_report(score_result, strategy_name)
```

WALK-FORWARD NOTE:
- Optimize trên data: {OPTIMIZE_START} → {OPTIMIZE_END}
- Validate trên data: {VALIDATE_START} → {VALIDATE_END}
- Nếu có thể, slice df theo date range trước khi backtest

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
- Strategy logic
- Entry/exit conditions  
- Risk management rules
- Parameter values

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

INPUT: Code Python backtesting đã được optimize + stats tốt nhất.

OUTPUT: File MQL5 (.mq5) bao gồm:

1. **Header & Properties**
   - #property copyright, version, description
   - #include <Trade/Trade.mqh>

2. **Input Parameters** (align với params đã optimize):
   - InpTenkan, InpKijun, InpSenkouB (Ichimoku)
   - InpEMAFast, InpEMASlow
   - InpRiskPct (% equity per trade)
   - InpSLPipsMultiplier
   - InpTPRR (Risk-Reward ratio)
   - InpMaxDD_Pct = {MAX_DRAWDOWN_PCT} (hard stop prop firm)
   - InpDailyLoss_Pct = {DAILY_LOSS_LIMIT_PCT}

3. **Global Variables**
   - CTrade trade object
   - iCustom handles (KHÔNG compute Ichimoku tay, dùng iCustom hoặc iIchimoku built-in)

4. **OnInit()**: Initialize indicator handles, validate params

5. **OnTick()**:
   - check_prop_firm_limits() → return nếu vi phạm DD
   - get_indicators() → lấy giá trị mới nhất
   - signal = get_signal() → BUY/SELL/NONE
   - Nếu có signal và không có position: open_trade(signal)
   - Trailing stop logic nếu có position

6. **Signal functions**:
   - is_above_cloud(), is_below_cloud()
   - tenkan_kijun_cross_up(), tenkan_kijun_cross_down()
   - ema_filter_bullish(), ema_filter_bearish()

7. **Risk Management**:
   - calculate_lot_size() theo % equity + SL distance
   - check_daily_loss_limit()
   - check_max_drawdown()

8. **Comments** đầy đủ bằng tiếng Việt.

QUAN TRỌNG:
- Dùng iIchimoku() built-in của MT5 (không dùng iCustom indicator ngoài)
- Tất cả magic numbers phải là named constants
- Code phải compile được trong MetaEditor
- Thêm comment: // Generated by MoonDev AI Agent — Comarai.com
"""

def get_model_id(model: str) -> str:
    return "DR" if "reasoner" in model else "DC"


# ═══════════════════════════════════════════════════════════════
# AI CLIENT INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def init_deepseek_client():
    key = os.getenv("DEEPSEEK_KEY")
    if not key:
        cprint("❌ DEEPSEEK_KEY không tìm thấy trong .env", "red")
        return None
    try:
        client = openai.OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
        cprint("✅ DeepSeek client ready!", "green")
        return client
    except Exception as e:
        cprint(f"❌ DeepSeek init error: {e}", "red")
        return None


def init_gemini_client():
    """Fallback: Google Gemini via openai-compatible endpoint."""
    try:
        import google.generativeai as genai
        key = os.getenv("GEMINI_KEY")
        if not key:
            cprint("⚠️ GEMINI_KEY không tìm thấy", "yellow")
            return None
        genai.configure(api_key=key)
        cprint("✅ Gemini client ready (fallback)!", "cyan")
        return genai
    except ImportError:
        cprint("⚠️ google-generativeai chưa cài: pip install google-generativeai", "yellow")
        return None


def chat_with_ai(system_prompt: str, user_content: str, model: str) -> str | None:
    """Chat với AI — DeepSeek primary, Gemini fallback."""
    cprint(f"\n🤖 Sending to {model}...", "yellow")

    # ── DeepSeek ────────────────────────────────────────────
    if "deepseek" in model.lower():
        client = init_deepseek_client()
        if client:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=AI_TEMPERATURE,
                    max_tokens=AI_MAX_TOKENS,
                )
                result = resp.choices[0].message.content.strip()
                cprint(f"✅ DeepSeek response: {len(result)} chars", "green")
                return result
            except Exception as e:
                cprint(f"❌ DeepSeek error: {e}", "red")
                if not USE_GEMINI_FALLBACK:
                    return None
                cprint("🔄 Switching to Gemini fallback...", "yellow")

    # ── Gemini Fallback ─────────────────────────────────────
    if USE_GEMINI_FALLBACK:
        genai = init_gemini_client()
        if genai:
            try:
                gmodel = genai.GenerativeModel(
                    model_name=GEMINI_FALLBACK_MODEL,
                    system_instruction=system_prompt,
                )
                resp = gmodel.generate_content(user_content)
                result = resp.text.strip()
                cprint(f"✅ Gemini fallback response: {len(result)} chars", "cyan")
                return result
            except Exception as e:
                cprint(f"❌ Gemini error: {e}", "red")

    cprint("❌ Tất cả AI models đều fail. Kiểm tra API keys trong .env", "red")
    return None


# ═══════════════════════════════════════════════════════════════
# PIPELINE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def extract_code(text: str) -> str:
    """Extract Python code từ markdown code blocks."""
    code_match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    # Fallback: nếu không có markdown, coi toàn bộ là code
    if "import " in text or "class " in text or "def " in text:
        return text.strip()
    return text.strip()


def extract_strategy_name(research_output: str) -> str:
    """Extract strategy name từ output của Research AI."""
    match = re.search(r"STRATEGY_NAME:\s*([A-Za-z0-9_]+)", research_output)
    if match:
        return match.group(1).strip()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return f"Strategy_{ts}"


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

    # Local PDF file
    if user_input.endswith(".pdf") and Path(user_input).exists():
        cprint(f"📄 Reading local PDF: {user_input}", "yellow")
        try:
            with open(user_input, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = " ".join(page.extract_text() or "" for page in reader.pages)
            return text
        except Exception as e:
            cprint(f"❌ Local PDF error: {e}", "red")
            return user_input

    # Plain text
    return user_input


def save_file(content: str, directory: Path, name: str, ext: str = "py") -> Path:
    """Lưu file và trả về path."""
    ts = datetime.now().strftime("%m%d_%H%M")
    filename = f"{name}_{ts}.{ext}"
    filepath = directory / filename
    filepath.write_text(content, encoding="utf-8")
    cprint(f"💾 Saved: {filepath}", "cyan")
    return filepath


def spinner(stop_event: threading.Event, label: str = "Thinking"):
    """Hiển thị spinner trong khi chờ AI."""
    chars = itertools.cycle(["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"])
    while not stop_event.is_set():
        print(f"\r🌙 {label} {next(chars)}", end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 40 + "\r", end="")


# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_rbi_pipeline(user_input: str):
    """
    Full 5-agent pipeline:
    Input → Research → Backtest → Debug → Package → MQL5 Export
    """
    cprint("\n" + "═"*60, "magenta")
    cprint("  🌙 MoonDev RBI Agent — Ichimoku + MQL5 Edition", "magenta", attrs=["bold"])
    cprint("═"*60 + "\n", "magenta")

    # ── Chuẩn bị input ──────────────────────────────────────
    content = get_input_content(user_input)
    if not content:
        cprint("❌ Không đọc được input content", "red")
        return

    # ── [1] Research AI ─────────────────────────────────────
    cprint("🔬 [1/5] Research AI đang phân tích strategy...", "cyan")
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(stop_event, "Research AI"), daemon=True)
    t.start()
    research_output = chat_with_ai(RESEARCH_PROMPT, content, RESEARCH_MODEL)
    stop_event.set()
    t.join()

    if not research_output:
        cprint("❌ Research AI failed", "red")
        return

    strategy_name = extract_strategy_name(research_output)
    cprint(f"✅ Strategy: {strategy_name}", "green")
    save_file(research_output, RESEARCH_DIR, strategy_name, ext="txt")

    # ── [2] Backtest AI ─────────────────────────────────────
    cprint(f"\n💻 [2/5] Backtest AI đang code {strategy_name}...", "cyan")
    data_path = DEFAULT_DATA_PATH
    xau_path = DATA_DIR / "XAUUSD-1H.csv"
    if xau_path.exists():
        data_path = xau_path

    backtest_input = f"""
Strategy Analysis:
{research_output}

Data path to use: {data_path}
Charts dir: {CHARTS_DIR}
Strategy name: {strategy_name}
"""
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(stop_event, "Backtest AI"), daemon=True)
    t.start()
    backtest_output = chat_with_ai(BACKTEST_PROMPT, backtest_input, BACKTEST_MODEL)
    stop_event.set()
    t.join()

    if not backtest_output:
        cprint("❌ Backtest AI failed", "red")
        return

    backtest_code = extract_code(backtest_output)
    backtest_file = save_file(backtest_code, BACKTEST_DIR, f"{strategy_name}_BT")

    # ── [3] Debug AI ─────────────────────────────────────────
    cprint(f"\n🐛 [3/5] Debug AI đang kiểm tra lỗi...", "cyan")
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(stop_event, "Debug AI"), daemon=True)
    t.start()
    debug_output = chat_with_ai(DEBUG_PROMPT, backtest_code, DEBUG_MODEL)
    stop_event.set()
    t.join()

    if debug_output:
        backtest_code = extract_code(debug_output)

    # ── [4] Package AI ───────────────────────────────────────
    cprint(f"\n📦 [4/5] Package AI đang clean backtesting.lib...", "cyan")
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(stop_event, "Package AI"), daemon=True)
    t.start()
    package_output = chat_with_ai(PACKAGE_PROMPT, backtest_code, BACKTEST_MODEL)
    stop_event.set()
    t.join()

    if package_output:
        backtest_code = extract_code(package_output)
        save_file(backtest_code, PACKAGE_DIR, f"{strategy_name}_PKG")

    # Final backtest file (ready to run)
    final_file = save_file(backtest_code, FINAL_DIR, f"{strategy_name}_BTFinal")

    # ── [5] MQL5 Export AI ──────────────────────────────────
    cprint(f"\n⚙️ [5/5] MQL5 Export AI đang generate .mq5...", "cyan")
    mql5_input = f"""
Strategy Name: {strategy_name}
Python Backtest Code:
{backtest_code}

Research Notes:
{research_output[:2000]}
"""
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(stop_event, "MQL5 Export AI"), daemon=True)
    t.start()
    mql5_output = chat_with_ai(EXPORT_MQL5_PROMPT, mql5_input, EXPORT_MQL5_MODEL)
    stop_event.set()
    t.join()

    if mql5_output:
        # Extract MQL5 code block
        mql5_code = re.search(r"```(?:mq5|cpp|c\+\+)?\n(.*?)```", mql5_output, re.DOTALL)
        mql5_str = mql5_code.group(1).strip() if mql5_code else mql5_output
        mql5_file = save_file(mql5_str, MQL5_DIR, f"{strategy_name}_EA", ext="mq5")
        cprint(f"✅ MQL5 EA saved: {mql5_file}", "green")
    else:
        cprint("⚠️ MQL5 Export skipped (AI failed)", "yellow")

    # ── Summary ─────────────────────────────────────────────
    cprint("\n" + "═"*60, "green")
    cprint(f"  ✅ Pipeline hoàn tất: {strategy_name}", "green", attrs=["bold"])
    cprint(f"  📁 Research:  {RESEARCH_DIR}", "white")
    cprint(f"  📁 Backtest:  {BACKTEST_DIR}", "white")
    cprint(f"  📁 Final:     {FINAL_DIR}", "white")
    cprint(f"  📁 MQL5 EA:  {MQL5_DIR}", "white")
    cprint(f"  📁 Charts:    {CHARTS_DIR}", "white")
    cprint("═"*60, "green")
    cprint("\n💡 Tiếp theo: chạy file BTFinal để xem composite score!", "yellow")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    cprint("🌙 MoonDev RBI Agent v2 — Ichimoku + MQL5 Export", "magenta", attrs=["bold"])
    cprint("=" * 60, "magenta")
    cprint("Input có thể là:", "cyan")
    cprint("  1. Text mô tả strategy (paste trực tiếp)", "white")
    cprint("  2. YouTube URL (transcript tự động)", "white")
    cprint("  3. PDF URL hoặc path file .pdf", "white")
    cprint("=" * 60, "magenta")

    user_input = input("\n🎯 Nhập strategy / URL: ").strip()
    if user_input:
        run_rbi_pipeline(user_input)
    else:
        cprint("❌ Input rỗng, thoát.", "red")
