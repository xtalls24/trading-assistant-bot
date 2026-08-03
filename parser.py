import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Currency pairs matching pattern (Explicit common pairs or valid symbol formats, with optional slash)
PAIR_PATTERN = re.compile(
    r"\b(EUR/?USD|GBP/?USD|AUD/?USD|USD/?CAD|USD/?JPY|USD/?CHF|NZD/?USD|EUR/?GBP|EUR/?JPY|GBP/?JPY|AUD/?JPY|EUR/?AUD|GBP/?AUD|AUD/?CAD|AUD/?NZD|CAD/?JPY|CHF/?JPY|EUR/?CAD|EUR/?CHF|EUR/?NZD|GBP/?CAD|GBP/?CHF|GBP/?NZD|NZD/?CAD|NZD/?CHF|NZD/?JPY|XAU/?USD|GOLD|XAG/?USD|BTC/?USD|ETH/?USD)\b",
    re.IGNORECASE,
)

# Direction matching pattern
DIRECTION_PATTERN = re.compile(r"\b(BUY|SELL|LONG|SHORT)\b", re.IGNORECASE)

# Numeric fields extraction pattern
ENTRY_PATTERN = re.compile(r"(?i)(?:entry|ep|open|\bat\b)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
SL_PATTERN = re.compile(r"(?i)(?:sl|stop|stop\s*loss)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
TP_PATTERN = re.compile(r"(?i)(?:tp|target|take\s*profit)\s*[:=\-]?\s*(\d+(?:\.\d+)?)")
RISK_PATTERN = re.compile(r"(?i)(?:risk|risk\s*amount)\s*[:=\-]?\s*(\d+(?:\.\d+)?\s*(?:%|\$|R)?)")
RR_PATTERN = re.compile(r"(?i)(?:risk[/:\-]reward|r[:/]r|planned\s*rr|\brr\b)\s*[:=\-]?\s*(?:1\s*[:/]\s*)?(\d+(?:\.\d+)?)", re.IGNORECASE)
MODEL_PATTERN = re.compile(r"(?i)(?:method|trading\s*model|model|setup|strategy)\s*[:=\-]?\s*([a-z0-9_\-\s]+)", re.IGNORECASE)
MODEL_SHORT_PATTERN = re.compile(r"(?i)\b(C1|C2|C3|SETUP\s*[A-Z0-9]+|MODEL\s*[A-Z0-9]+)\b")

# Result & Realized R extraction patterns
RESULT_KEYWORD_PATTERN = re.compile(r"(?i)(?:final\s*result|outcome|result|status)\s*[:=\-]?\s*(TP|SL|BE|WIN|LOSS|BREAKEVEN)", re.IGNORECASE)
REALIZED_R_PATTERN = re.compile(r"(?i)(?:realized\s*r|realized|pnl|actual\s*r)\s*[:=\-]?\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
R_STANDALONE_PATTERN = re.compile(r"([+-]\d+(?:\.\d+)?)\s*R\b", re.IGNORECASE)

# Standalone result reply pattern (e.g., "TP +3R", "SL -1R", "BE", "+3R")
RESULT_REPLY_PATTERN = re.compile(
    r"(?i)^\s*(TP|SL|BE|WIN|LOSS|BREAKEVEN)?\s*([+-]?\d+(?:\.\d+)?)?\s*R?\s*$"
)
SIMPLE_R_PATTERN = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)R\s*$", re.IGNORECASE)


def parse_trade_journal(text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single trade journal post (finished trade or open trade setup).
    Returns a dict with all extracted trade details and result status, or None.
    """
    if not text:
        return None

    # Check for Pair and Direction
    pair_match = PAIR_PATTERN.search(text)
    direction_match = DIRECTION_PATTERN.search(text)

    is_journal_keyword = bool(
        re.search(
            r"(?i)\b(BEFORE|AFTER|JOURNAL|TRADE|SETUP|ANALYSIS|ENTRY|RESULT|MODEL|PAIR)\b",
            text,
        )
    )

    if not (pair_match or direction_match or is_journal_keyword):
        return None

    raw_pair = pair_match.group(1).upper().replace("/", "") if pair_match else "UNKNOWN"
    pair = "XAUUSD" if raw_pair == "GOLD" else raw_pair

    direction = "BUY"
    if direction_match:
        dir_str = direction_match.group(1).upper()
        if dir_str in ("SHORT", "SELL"):
            direction = "SELL"
        else:
            direction = "BUY"

    # Extract model
    model = "SETUP"
    model_match = MODEL_PATTERN.search(text)
    if model_match:
        # Extract first line/word of model value
        model_val = model_match.group(1).strip().split("\n")[0].strip().upper()
        if model_val:
            model = model_val
    else:
        model_short = MODEL_SHORT_PATTERN.search(text)
        if model_short:
            model = model_short.group(1).upper()

    # Extract optional numerical entry parameters
    entry_match = ENTRY_PATTERN.search(text)
    sl_match = SL_PATTERN.search(text)
    tp_match = TP_PATTERN.search(text)
    risk_match = RISK_PATTERN.search(text)
    rr_match = RR_PATTERN.search(text)

    entry_price = float(entry_match.group(1)) if entry_match else None
    stop_loss = float(sl_match.group(1)) if sl_match else None
    take_profit = float(tp_match.group(1)) if tp_match else None
    risk_input = risk_match.group(1) if risk_match else None
    planned_rr = float(rr_match.group(1)) if rr_match else None

    if planned_rr is None and entry_price and stop_loss and take_profit:
        risk_dist = abs(entry_price - stop_loss)
        reward_dist = abs(take_profit - entry_price)
        if risk_dist > 0:
            planned_rr = round(reward_dist / risk_dist, 2)

    # Extract Result & Realized R
    res_match = RESULT_KEYWORD_PATTERN.search(text)
    realized_r_match = REALIZED_R_PATTERN.search(text)
    r_standalone_match = R_STANDALONE_PATTERN.search(text)

    result = None
    actual_r = None

    if res_match:
        res_str = res_match.group(1).upper()
        if res_str in ("TP", "WIN"):
            result = "TP"
        elif res_str in ("SL", "LOSS"):
            result = "SL"
        elif res_str in ("BE", "BREAKEVEN"):
            result = "BE"

    if realized_r_match:
        try:
            actual_r = float(realized_r_match.group(1))
        except ValueError:
            pass
    elif r_standalone_match:
        try:
            actual_r = float(r_standalone_match.group(1))
        except ValueError:
            pass
    else:
        # Check for format like "RESULT : TP +2R" or "RESULT: TP 2R"
        tp_plus_r = re.search(r"(?i)(?:result|outcome|status)\s*[:=\-]?\s*(TP|SL|BE|WIN|LOSS)\s*([+-]?\d+(?:\.\d+)?)?\s*R?", text)
        if tp_plus_r:
            res_str = tp_plus_r.group(1).upper()
            r_str = tp_plus_r.group(2)
            if res_str in ("TP", "WIN"):
                result = "TP"
            elif res_str in ("SL", "LOSS"):
                result = "SL"
            elif res_str in ("BE", "BREAKEVEN"):
                result = "BE"

            if r_str and actual_r is None:
                try:
                    actual_r = float(r_str)
                except ValueError:
                    pass

    # Fallback result lookup from general text if not matched by explicit key
    if not result:
        if re.search(r"(?i)\b(TP|TAKE\s*PROFIT|WIN)\b", text) and re.search(r"(?i)\b(RESULT|OUTCOME|FINAL|STATUS)\b", text):
            result = "TP"
        elif re.search(r"(?i)\b(SL|STOP\s*LOSS|LOSS)\b", text) and re.search(r"(?i)\b(RESULT|OUTCOME|FINAL|STATUS)\b", text):
            result = "SL"
        elif re.search(r"(?i)\b(BE|BREAKEVEN)\b", text) and re.search(r"(?i)\b(RESULT|OUTCOME|FINAL|STATUS)\b", text):
            result = "BE"

    # Synchronize result and actual_r defaults
    if actual_r is not None and result is None:
        if actual_r > 0:
            result = "TP"
        elif actual_r < 0:
            result = "SL"
        else:
            result = "BE"

    if result is not None and actual_r is None:
        if result == "TP":
            actual_r = planned_rr or 2.0
        elif result == "SL":
            actual_r = -1.0
        elif result == "BE":
            actual_r = 0.0

    status = "CLOSED" if result is not None else "OPEN"

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
        "status": status,
        "result": result,
        "actual_r": actual_r,
    }


def parse_trade_result(text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a reply message or outcome update resolving a trade
    (e.g. "TP +2R", "SL -1R", "BE", "TP", "SL", "+2R", "HIT TP", "RESULT : TP +2R", "EURUSD TP +2R").
    Returns a dict with 'result' (TP/SL/BE) and 'actual_r' (float), or None if not recognized.
    """
    if not text:
        return None

    cleaned = text.strip().upper()

    # 1. Direct short strings
    if cleaned in ("BE", "BREAKEVEN", "0R", "+0R", "-0R"):
        return {"result": "BE", "actual_r": 0.0}
    if cleaned in ("TP", "WIN", "TARGET", "HIT TP"):
        return {"result": "TP", "actual_r": 2.0}
    if cleaned in ("SL", "LOSS", "STOP", "HIT SL"):
        return {"result": "SL", "actual_r": -1.0}

    # 2. Check for explicit result + R pattern anywhere in text
    # e.g., "TP +2R", "TP 2R", "SL -1R", "BE 0R", "HIT TP +3.5R", "RESULT: TP +2R"
    match_tp_r = re.search(r"(?i)\b(TP|WIN|TARGET)\b\s*([+-]?\d+(?:\.\d+)?)?\s*R?\b", text)
    match_sl_r = re.search(r"(?i)\b(SL|LOSS|STOP)\b\s*([+-]?\d+(?:\.\d+)?)?\s*R?\b", text)
    match_be_r = re.search(r"(?i)\b(BE|BREAKEVEN)\b\s*([+-]?\d+(?:\.\d+)?)?\s*R?\b", text)

    # 3. Check for standalone R value like "+2R", "-1R", "+2.5R"
    match_r_only = re.search(r"(?i)(?:\b|\s)([+-]\d+(?:\.\d+)?)\s*R\b", text)

    if match_tp_r:
        r_str = match_tp_r.group(2)
        actual_r = float(r_str) if r_str else 2.0
        if actual_r < 0:
            actual_r = abs(actual_r)
        return {"result": "TP", "actual_r": actual_r}

    if match_sl_r:
        r_str = match_sl_r.group(2)
        actual_r = float(r_str) if r_str else -1.0
        if actual_r > 0:
            actual_r = -actual_r
        return {"result": "SL", "actual_r": actual_r}

    if match_be_r:
        r_str = match_be_r.group(2)
        actual_r = float(r_str) if r_str else 0.0
        return {"result": "BE", "actual_r": actual_r}

    if match_r_only:
        val = float(match_r_only.group(1))
        if val > 0:
            return {"result": "TP", "actual_r": val}
        elif val < 0:
            return {"result": "SL", "actual_r": val}
        else:
            return {"result": "BE", "actual_r": 0.0}

    return None

