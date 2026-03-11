<div align="center">

# 🤖 MoonDev AI Trading Agents
### Fork & Tối Ưu: Ichimoku + MQL5 Backtest Pipeline

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%20%7C%20Gemini-purple)](https://platform.deepseek.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Comarai](https://img.shields.io/badge/Built%20by-Comarai.com-orange)](https://comarai.com)

</div>

---

## 🎯 Repo này là gì?

Fork & nâng cấp từ [CurvedLightGroup/MoonDev-Trading-Ai-Agents](https://github.com/CurvedLightGroup/MoonDev-Trading-Ai-Agents).

**Điểm khác biệt so với repo gốc:**

| Feature | Gốc (MoonDev) | Fork này |
|---|---|---|
| Target instrument | Solana tokens | **Forex / XAU / BTC** |
| AI Model | DeepSeek only | **DeepSeek + Gemini fallback** |
| Backtest strategy | Generic EMA/Momentum | **Ichimoku + EMA200 filter** |
| Scoring system | Không có | **Composite scoring (Balance>PF>RF>MaxDD)** |
| MQL5 export | Không có | **Agent thứ 5: .mq5 skeleton** |
| Windows support | Broken (path macOS) | **Native Windows paths** |
| TA Library | TA-Lib (cần binary) | **pandas-ta (pip install)** |

---

## 🧠 Tư Duy Thiết Kế

> *Repo gốc build AI agent để trade Solana memecoin. Tôi cần pipeline khác: nghiên cứu chiến lược → backtest Python → score → export MQL5 EA — rồi backtest thật trong MT5 trước khi chạy live. Đây là tinh thần của MQL5 Strategy Tester.*

**Pipeline 5 agents:**
```
Input (text / YouTube / PDF)
  ↓ [1] Research AI   → Phân tích strategy, extract rules
  ↓ [2] Backtest AI   → Code backtesting.py + Ichimoku
  ↓ [3] Debug AI      → Fix lỗi kỹ thuật
  ↓ [4] Package AI    → Clean code, bỏ backtesting.lib
  ↓ [5] MQL5 Export  → Generate .mq5 skeleton (MỚI)
         + Composite Score Report
```

**Scoring system** (giống MT5 Optimizer):
```
Score = 0.4 × Return% + 0.3 × ProfitFactor + 0.2 × RecoveryFactor - 0.1 × MaxDD
```

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/hungpixi/moondev-agent.git
cd moondev-agent

# 2. Cài dependencies (Windows-friendly)
pip install -r requirements.txt

# 3. Setup API keys
cp .env.example .env
# Mở .env, điền DEEPSEEK_KEY và GEMINI_KEY

# 4. Chạy RBI Agent
python src/agents/rbi_agent.py

# 5. (Optional) Download data XAUUSD
python src/data/ohlcv_collector.py

# 6. (Optional) Chạy backtest mẫu Ichimoku
python src/data/rbi/backtests/IchiDCA_Template_BT.py
```

---

## 📁 Cấu Trúc

```
moondev-agent/
├── src/
│   ├── agents/
│   │   ├── rbi_agent.py          ← Pipeline chính (5 agents)
│   │   ├── risk_agent.py         ← Quản lý risk portfolio
│   │   ├── trading_agent.py      ← Trade agent (Solana)
│   │   └── ...                   ← Các agent gốc khác
│   ├── data/
│   │   ├── ohlcv_collector.py    ← Download XAUUSD/BTC/FX (yfinance)
│   │   ├── composite_scorer.py   ← Scoring system (MQL5 style)
│   │   └── rbi/
│   │       ├── backtests/        ← AI-generated backtest code
│   │       ├── backtests_final/  ← Final clean backtest
│   │       ├── mql5_exports/     ← .mq5 skeleton files (MỚI)
│   │       ├── research/         ← AI research notes
│   │       └── charts/           ← HTML interactive charts
│   └── config.py                 ← Cấu hình tập trung
├── context.md                    ← Context cá nhân (gitignored)
├── .env.example                  ← API key template
└── requirements.txt
```

---

## 🔮 Roadmap

- [ ] Walk-forward validation tự động (Q4 2025 → Q1 2026)
- [ ] Multi-instrument comparison (XAUUSD vs BTCUSD vs EURUSD)
- [ ] Dashboard hiển thị composite scores
- [ ] Auto-push kết quả tốt nhất vào MT5 via Python-MT5 bridge
- [ ] Telegram notification khi backtest hoàn tất

---

## 📚 Nguồn Tham Khảo

- Repo gốc: [CurvedLightGroup/MoonDev-Trading-Ai-Agents](https://github.com/CurvedLightGroup/MoonDev-Trading-Ai-Agents)
- Backtesting framework: [kernc/backtesting.py](https://github.com/kernc/backtesting.py)
- Ichimoku reference: Goichi Hosoda

---

## 🤝 Bạn Muốn Hệ Thống Trading AI Tương Tự?

| Bạn cần | Chúng tôi đã làm ✅ |
|---|---|
| AI Agent phân tích & backtest | ✅ RBI Pipeline 5 agents |
| Export chiến lược sang MQL5 EA | ✅ MQL5 Export Agent |
| Prop Firm risk management | ✅ DD/Daily Loss guard |
| Composite scoring như MT5 | ✅ Balance>PF>RF>MaxDD |
| Auto trade execution | 🔄 Đang phát triển |

<div align="center">

[🌐 Yêu cầu Demo](https://comarai.com) · [💬 Zalo](https://zalo.me/0834422439) · [📧 Email](mailto:hungphamphunguyen@gmail.com)

**Comarai — AI Automation Agency**  
*Em Sale · Em Content · Em Marketing · Em Trade*

> Trade thông minh hơn, không phải chăm chỉ hơn. AI làm 80% việc nặng cho bạn.

</div>

---

*Built by [hungpixi](https://github.com/hungpixi) · Powered by [Comarai.com](https://comarai.com)*