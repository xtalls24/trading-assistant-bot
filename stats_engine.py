import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_statistics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes comprehensive trading statistics from a list of trade dictionaries.
    Only closed trades (with result or actual_r) are evaluated for performance metrics.
    """
    closed_trades = [
        t for t in trades if t.get("status") == "CLOSED" or t.get("result") or t.get("actual_r") is not None
    ]
    total_all = len(trades)
    total_closed = len(closed_trades)

    if total_closed == 0:
        return {
            "total_all": total_all,
            "total": 0,
            "wins": 0,
            "losses": 0,
            "be": 0,
            "win_rate": 0.0,
            "avg_rr": 0.0,
            "avg_r": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "net_r": 0.0,
        }

    wins_list = []
    losses_list = []
    be_count = 0
    all_actual_r = []
    all_planned_rr = []

    for t in trades:
        planned_rr = t.get("planned_rr") or t.get("rr")
        if planned_rr is not None:
            try:
                all_planned_rr.append(float(planned_rr))
            except (ValueError, TypeError):
                pass

    for t in closed_trades:
        res = (t.get("result") or "").upper()
        actual_r = t.get("actual_r")

        if actual_r is not None:
            try:
                r_val = float(actual_r)
            except (ValueError, TypeError):
                r_val = 0.0

            all_actual_r.append(r_val)
            if r_val > 0:
                wins_list.append(r_val)
            elif r_val < 0:
                losses_list.append(r_val)
            else:
                be_count += 1
        elif res in ("TP", "WIN"):
            r_val = float(t.get("planned_rr") or 2.0)
            wins_list.append(r_val)
            all_actual_r.append(r_val)
        elif res in ("SL", "LOSS"):
            r_val = -1.0
            losses_list.append(r_val)
            all_actual_r.append(r_val)
        elif res in ("BE", "BREAKEVEN"):
            be_count += 1
            all_actual_r.append(0.0)

    wins = len(wins_list)
    losses = len(losses_list)
    win_rate = round((wins / total_closed) * 100, 2) if total_closed > 0 else 0.0

    avg_rr = round(sum(all_planned_rr) / len(all_planned_rr), 2) if all_planned_rr else 0.0
    avg_r = round(sum(all_actual_r) / total_closed, 2) if total_closed > 0 else 0.0

    gross_profit = sum(wins_list)
    gross_loss = abs(sum(losses_list))
    profit_factor = (
        round(gross_profit / gross_loss, 2)
        if gross_loss > 0
        else (round(gross_profit, 2) if gross_profit > 0 else 0.0)
    )

    avg_win = (gross_profit / wins) if wins > 0 else 0.0
    avg_loss = (gross_loss / losses) if losses > 0 else 0.0
    win_prob = wins / total_closed if total_closed > 0 else 0.0
    loss_prob = losses / total_closed if total_closed > 0 else 0.0
    expectancy = round((win_prob * avg_win) - (loss_prob * avg_loss), 2)

    largest_win = round(max(wins_list), 2) if wins_list else 0.0
    largest_loss = round(min(losses_list), 2) if losses_list else 0.0
    net_r = round(sum(all_actual_r), 2)

    return {
        "total_all": total_all,
        "total": total_closed,
        "wins": wins,
        "losses": losses,
        "be": be_count,
        "win_rate": win_rate,
        "avg_rr": avg_rr,
        "avg_r": avg_r,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "net_r": net_r,
    }


def format_stats_report(title: str, stats: Dict[str, Any]) -> str:
    """
    Formats a stats dictionary into a clean Telegram Markdown report.
    """
    if stats["total"] == 0:
        return f"📊 *{title}*\n\nBelum ada trade yang selesai (CLOSED) pada periode ini."

    return (
        f"📊 *{title}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 *Total Closed Trades:* {stats['total']}\n"
        f"✅ *Wins:* {stats['wins']} | ❌ *Losses:* {stats['losses']} | ➖ *BE:* {stats['be']}\n"
        f"📈 *Win Rate:* `{stats['win_rate']}%` \n"
        f"💰 *Net R:* `{stats['net_r']:+}R` \n\n"
        f"⚖️ *Avg RR:* `{stats['avg_rr']}R` | *Avg R/Trade:* `{stats['avg_r']}R` \n"
        f"🔥 *Profit Factor:* `{stats['profit_factor']}` \n"
        f"🎯 *Expectancy:* `{stats['expectancy']}R / trade` \n"
        f"🏆 *Largest Win:* `+{stats['largest_win']}R` \n"
        f"⚠️ *Largest Loss:* `{stats['largest_loss']}R` \n"
    )


def compute_group_breakdown(
    trades: List[Dict[str, Any]], group_by_key: str
) -> Dict[str, Dict[str, Any]]:
    """
    Groups trades by a specified key ('pair', 'model', 'weekday', 'month') and computes stats per group.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for t in trades:
        if group_by_key == "weekday":
            created_at_str = t.get("created_at") or t.get("date") or ""
            try:
                if "T" in created_at_str or " " in created_at_str:
                    dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(created_at_str, "%Y-%m-%d")
                key = dt.strftime("%A")
            except Exception:
                key = "Unknown"
        elif group_by_key == "month":
            created_at_str = t.get("created_at") or t.get("date") or ""
            try:
                if "T" in created_at_str or " " in created_at_str:
                    dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(created_at_str, "%Y-%m-%d")
                key = dt.strftime("%B %Y")
            except Exception:
                key = "Unknown"
        else:
            key = str(t.get(group_by_key) or "Unknown").upper()

        groups.setdefault(key, []).append(t)

    result = {}
    for key, group_trades in groups.items():
        result[key] = compute_statistics(group_trades)

    return result
