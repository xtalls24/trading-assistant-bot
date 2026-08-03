import sys
sys.path.insert(0, "/root/trading-assistant-bot")

from parser import parse_trade_journal

user_text = """EURUSD BUY SETUP

METHOD: C2 MODEL
-BIAS H1 BULLISH
-FVG H1
-CONFIRM M15 MSS+CISD+FVG
-LONDON KZ

RR 1:2

RESULT : TP +2R"""

result = parse_trade_journal(user_text)
print("Parsing User Format Result:")
for k, v in result.items():
    print(f"  {k}: {v}")
