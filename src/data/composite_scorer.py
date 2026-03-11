"""
🧮 Composite Scorer — MQL5 Style Strategy Evaluation
Chấm điểm backtest theo tinh thần: Balance > PF > RF > MaxDD
Tương tự optimization scoring trong MT5.
"""

import sys
from pathlib import Path
from termcolor import cprint

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from config import SCORE_WEIGHTS, MIN_PROFIT_FACTOR, MIN_RECOVERY_FACTOR, MAX_ALLOWED_DD_PCT


def composite_score(stats: dict) -> dict:
    """
    Tính composite score từ kết quả backtest (backtesting.py stats dict).
    
    Args:
        stats: dict với keys từ backtesting.py stats object, ví dụ:
               stats['Return [%]'], stats['Profit Factor'], ...
               Có thể dùng vars(stats) hoặc dict(stats) từ bt.run()
    
    Returns:
        dict {
            'score': float,        # Điểm tổng hợp (cao hơn = tốt hơn)
            'passed': bool,        # True nếu vượt các ngưỡng filter
            'breakdown': dict,     # Chi tiết từng thành phần
            'verdict': str,        # 'PASS' | 'FAIL' | 'WARNING'
        }
    """
    # Extract metrics (với fallback về 0)
    ret_pct      = float(stats.get("Return [%]", 0))
    profit_factor = float(stats.get("Profit Factor", 0))
    recovery_factor = float(stats.get("Recovery Factor", 0))
    max_dd_pct   = abs(float(stats.get("Max. Drawdown [%]", 100)))
    num_trades   = int(stats.get("# Trades", 0))
    win_rate     = float(stats.get("Win Rate [%]", 0))
    sharpe       = float(stats.get("Sharpe Ratio", 0))

    # ── Filter checks ──────────────────────────────────────────
    filters_passed = []
    filters_failed = []

    if profit_factor >= MIN_PROFIT_FACTOR:
        filters_passed.append(f"PF {profit_factor:.2f} ≥ {MIN_PROFIT_FACTOR}")
    else:
        filters_failed.append(f"PF {profit_factor:.2f} < {MIN_PROFIT_FACTOR} (FAIL)")

    if recovery_factor >= MIN_RECOVERY_FACTOR:
        filters_passed.append(f"RF {recovery_factor:.2f} ≥ {MIN_RECOVERY_FACTOR}")
    else:
        filters_failed.append(f"RF {recovery_factor:.2f} < {MIN_RECOVERY_FACTOR} (FAIL)")

    if max_dd_pct <= MAX_ALLOWED_DD_PCT:
        filters_passed.append(f"MaxDD {max_dd_pct:.1f}% ≤ {MAX_ALLOWED_DD_PCT}%")
    else:
        filters_failed.append(f"MaxDD {max_dd_pct:.1f}% > {MAX_ALLOWED_DD_PCT}% (FAIL)")

    if num_trades < 10:
        filters_failed.append(f"Too few trades: {num_trades} < 10")

    passed = len(filters_failed) == 0

    # ── Composite score calculation ────────────────────────────
    # Normalize các thành phần về [0, 100] trước khi weight
    # Return: thường 0-200% → normalize qua 100
    ret_norm    = min(ret_pct / 100.0, 2.0) * 50       # Max 100 points
    pf_norm     = min(profit_factor / 3.0, 1.0) * 100  # PF=3 → 100pts
    rf_norm     = min(recovery_factor / 5.0, 1.0) * 100 # RF=5 → 100pts
    dd_penalty  = (max_dd_pct / MAX_ALLOWED_DD_PCT) * 100  # 0-100, higher worse

    raw_score = (
        SCORE_WEIGHTS["return_pct"]       * ret_norm    +
        SCORE_WEIGHTS["profit_factor"]    * pf_norm     +
        SCORE_WEIGHTS["recovery_factor"]  * rf_norm     +
        SCORE_WEIGHTS["max_drawdown"]     * dd_penalty  # negative weight
    )

    # ── Verdict ────────────────────────────────────────────────
    if not passed:
        verdict = "❌ FAIL"
    elif raw_score >= 50:
        verdict = "✅ PASS (Excellent)"
    elif raw_score >= 30:
        verdict = "⚠️ PASS (Acceptable)"
    else:
        verdict = "⚠️ WARNING (Weak)"

    breakdown = {
        "Return [%]":        ret_pct,
        "Profit Factor":     profit_factor,
        "Recovery Factor":   recovery_factor,
        "Max DD [%]":        max_dd_pct,
        "# Trades":          num_trades,
        "Win Rate [%]":      win_rate,
        "Sharpe Ratio":      sharpe,
        "Ret_Normalized":    ret_norm,
        "PF_Normalized":     pf_norm,
        "RF_Normalized":     rf_norm,
        "DD_Penalty":        dd_penalty,
    }

    return {
        "score":            round(raw_score, 4),
        "passed":           passed,
        "breakdown":        breakdown,
        "verdict":          verdict,
        "filters_passed":   filters_passed,
        "filters_failed":   filters_failed,
    }


def print_score_report(result: dict, strategy_name: str = "Strategy"):
    """In báo cáo score đẹp ra console."""
    score = result["score"]
    verdict = result["verdict"]
    breakdown = result["breakdown"]

    print("\n" + "═" * 55)
    cprint(f"  🏆 {strategy_name} — COMPOSITE SCORE", "magenta", attrs=["bold"])
    print("═" * 55)
    cprint(f"  Score:    {score:.4f}   {verdict}", "white", attrs=["bold"])
    print("─" * 55)

    rows = [
        ("Return",          f"{breakdown['Return [%]']:.2f}%",       "Return [%]"),
        ("Profit Factor",   f"{breakdown['Profit Factor']:.3f}",      "Profit Factor"),
        ("Recovery Factor", f"{breakdown['Recovery Factor']:.3f}",    "Recovery Factor"),
        ("Max Drawdown",    f"{breakdown['Max DD [%]']:.2f}%",        "Max DD [%]"),
        ("# Trades",        f"{int(breakdown['# Trades'])}",          "# Trades"),
        ("Win Rate",        f"{breakdown['Win Rate [%]']:.1f}%",      "Win Rate [%]"),
        ("Sharpe Ratio",    f"{breakdown['Sharpe Ratio']:.3f}",       "Sharpe Ratio"),
    ]
    for label, value, _ in rows:
        cprint(f"  {label:<18} {value:>10}", "cyan")

    print("─" * 55)
    if result["filters_passed"]:
        for msg in result["filters_passed"]:
            cprint(f"  ✅ {msg}", "green")
    if result["filters_failed"]:
        for msg in result["filters_failed"]:
            cprint(f"  ❌ {msg}", "red")
    print("═" * 55 + "\n")


def rank_strategies(results: list[dict]) -> list[dict]:
    """
    Rank danh sách kết quả chiến lược theo composite score.
    
    Args:
        results: list of {name, stats} dicts
    
    Returns:
        list sorted by score descending, chỉ PASS
    """
    scored = []
    for item in results:
        score_result = composite_score(item["stats"])
        scored.append({
            "name":    item["name"],
            "score":   score_result["score"],
            "passed":  score_result["passed"],
            "verdict": score_result["verdict"],
            "details": score_result,
        })

    # Sort: PASS first, then by score desc
    scored.sort(key=lambda x: (not x["passed"], -x["score"]))
    return scored


if __name__ == "__main__":
    # Quick test với mock data
    mock_stats = {
        "Return [%]":           85.0,
        "Profit Factor":         1.8,
        "Recovery Factor":       2.1,
        "Max. Drawdown [%]":   -12.5,
        "# Trades":              47,
        "Win Rate [%]":         58.0,
        "Sharpe Ratio":          1.3,
    }
    result = composite_score(mock_stats)
    print_score_report(result, "IchiDCA_XAUUSD_Test")
