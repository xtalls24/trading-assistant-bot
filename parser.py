import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Currency pairs matching pattern (Explicit common pairs or valid symbol formats)
PAIR_PATTERN = re.compile(
    r"\b(EURUSD|GBPUSD|AUDUSD|USDCAD|USDJPY|USDCHF|NZDUSD|EURGBP|EURJPY|GBPJPY|AUDJPY|EURAUD|GBPAUD|AUDCAD|AUDNZD|CADJPY|CHFJPY|EURAUD|EURCAD|EURCHF|EURNZD|GBPCAD|GBPCHF|GBPNZD|NZDCAD|NZDCHF|NZDJPY|XAUUSD|XAGUSD|BTCUSD|ETHUSD)\b",
    re.IGNORECASE,
)

# Direction matching pattern
DIRECTION_PATTERN = re.compile(r"\b(BUY|SELL|LONG|SHORT)\b", re.IGNORECASE)

# Numeric fields extraction pattern
ENTRY_PATTERN = re.compile(r"(?i)(?:entry|ep|open|\bat\b)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
SL_PATTERN = re.compile(r"(?i)(?:sl|stop|stop\s*loss)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
TP_PATTERN = re.compile(r"(?i)(?:tp|target|take\s*profit)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
RISK_PATTERN = re.compile(r"(?i)(?:risk|risk\s*amount)\s*[:=\-]?\s*(\d+(?:\.\d+)?\s*(?:%|\$|R)?)")
RR_PATTERN = re.compile(r"(?i)(?:rr|r:r|risk\s*reward)\s*[:=\-]?\s*1?\s*[:/]?\s*(\d+(?:\.\d+)?)")
MODEL_PATTERN = re.compile(r"(?i)\b(C1|C2|C3|SETUP\s*[A-C]|MODEL\s*[1-3])\b")

# Trade Result reply pattern (e.g., "TP +3R", "SL -1R", "BE", "TP +2.5R", "SL", "TP", "+3R", "-1R")
RESULT_REPLY_PATTERN = re.compile(
    r"(?i)^\s*(TP|SL|BE|WIN|LOSS|BREAKEVEN)?\s*([+-]?\d+(?:\.\d+)?)?\s*R?\s*$"
)

SIMPLE_R_PATTERN = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)R\s*$", re.IGNORECASE)


def parse_trade_journal(text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a BEFORE TRADE message post.
    Returns a dict with parsed fields if a valid trade post is detected, else None.
    """
    if not text:
        return None

    # Check for Pair and Direction (Mandatory for a valid auto-detected trade)
    pair_match = PAIR_PATTERN.search(text)
    direction_match = DIRECTION_PATTERN.search(text)

    # Must contain pair & direction OR explicitly mention BEFORE TRADE / JOURNAL / TRADE
    is_journal_keyword = bool(
        re.search(
            r"(?i)\b(BEFORE\s*TRADE|JOURNAL|NEW\s*TRADE|TRADE\s*SETUP|ANALYSIS)\b",
            text,
        )
    )

    if not (pair_match and direction_match) and not is_journal_keyword:
        return None

    # Ignore text if it looks purely like a result reply (e.g., TP +3R, BE)
    if parse_trade_result(text) and not pair_match:
        return None

    pair = pair_match.group(1).upper() if pair_match else "UNKNOWN"
    direction = direction_match.group(1).upper() if direction_match else "BUY"
    if direction in ("LONG", "BUY"):
        direction = "BUY"
    elif direction in ("SHORT", "SELL"):
        direction = "SELL"

    # Extract optional numerical entry parameters
    entry_match = ENTRY_PATTERN.search(text)
    sl_match = SL_PATTERN.search(text)
    tp_match = TP_PATTERN.search(text)
    risk_match = RISK_PATTERN.search(text)
    rr_match = RR_PATTERN.search(text)
    model_match = MODEL_PATTERN.search(text)

    entry_price = float(entry_match.group(1)) if entry_match else None
    stop_loss = float(sl_match.group(1)) if sl_match else None
    take_profit = float(tp_match.group(1)) if tp_match else None
    risk_input = risk_match.group(1) if risk_match else None
    planned_rr = float(rr_match.group(1)) if rr_match else None
    model = model_match.group(1).upper() if model_match else "SETUP"

    # Calculate planned RR automatically if Entry, SL, and TP are present
    if planned_rr is None and entry_price and stop_loss and take_profit:
        risk_dist = abs(entry_price - stop_loss)
        reward_dist = abs(take_profit - entry_price)
        if risk_dist > 0:
            planned_rr = round(reward_dist / risk_dist, 2)

    return {
        "pair": pair,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_input": risk_input,
        "planned_rr": planned_rr or 2.0,
        "model": model,
        "notes": text.strip(),
    }


def parse_trade_result(text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a reply message resolving a trade (e.g. "TP +3R", "SL -1R", "BE", "TP", "SL", "+3.5R").
    Returns a dict with 'result' (TP/SL/BE) and 'actual_r' (float), or None if not recognized.
    """
    if not text:
        return None

    cleaned = text.strip().upper()

    # 1. Direct keywords
    if cleaned in ("BE", "BREAKEVEN", "0R", "+0R", "-0R"):
        return {"result": "BE", "actual_r": 0.0}
    if cleaned in ("TP", "WIN", "TARGET"):
        return {"result": "TP", "actual_r": 2.0}
    if cleaned in ("SL", "LOSS", "STOP"):
        return {"result": "SL", "actual_r": -1.0}

    # 2. Check simple "+3R", "-1R", "2.5R"
    simple_match = SIMPLE_R_PATTERN.match(cleaned)
    if simple_match:
        val = float(simple_match.group(1))
        if val > 0:
            return {"result": "TP", "actual_r": val}
        elif val < 0:
            return {"result": "SL", "actual_r": val}
        else:
            return {"result": "BE", "actual_r": 0.0}

    # 3. Check combined "TP +3R", "SL -1.5R", "BE +0.5R"
    match = RESULT_REPLY_PATTERN.match(cleaned)
    if match:
        res_type = match.group(1)
        r_val_str = match.group(2)

        if not res_type and not r_val_str:
            return None

        if res_type in ("BE", "BREAKEVEN"):
            actual_r = float(r_val_str) if r_val_str else 0.0
            return {"result": "BE", "actual_r": actual_r}

        if res_type in ("TP", "WIN"):
            actual_r = float(r_val_str) if r_val_str else 2.0
            if actual_r < 0:
                actual_r = abs(actual_r)
            return {"result": "TP", "actual_r": actual_r}

        if res_type in ("SL", "LOSS"):
            actual_r = float(r_val_str) if r_val_str else -1.0
            if actual_r > 0:
                actual_r = -actual_r
            return {"result": "SL", "actual_r": actual_r}

        # If res_type is None but r_val_str is present
        if r_val_str:
            val = float(r_val_str)
            if val > 0:
                return {"result": "TP", "actual_r": val}
            elif val < 0:
                return {"result": "SL", "actual_r": val}
            else:
                return {"result": "BE", "actual_r": 0.0}

    return None
