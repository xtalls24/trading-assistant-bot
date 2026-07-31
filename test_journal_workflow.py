import os
import sys
import unittest

sys.path.insert(0, "/root/trading-assistant-bot")

from parser import parse_trade_journal, parse_trade_result
from stats_engine import compute_statistics, format_stats_report, compute_group_breakdown
from database import Database
from config import Config

class TestJournalWorkflow(unittest.TestCase):
    def test_parser_sample_1(self):
        text = """EUR/USD BUY SETUP
Trading Model: C2 Model
Reason: H1 Bullish FVG + M15 CISD
Risk/Reward: 1:3
Final Result: TP
Realized R: +3R"""
        res = parse_trade_journal(text)
        self.assertIsNotNone(res)
        self.assertEqual(res["pair"], "EURUSD")
        self.assertEqual(res["direction"], "BUY")
        self.assertEqual(res["planned_rr"], 3.0)
        self.assertEqual(res["status"], "CLOSED")
        self.assertEqual(res["result"], "TP")
        self.assertEqual(res["actual_r"], 3.0)

    def test_parser_sample_2(self):
        text = """XAUUSD SHORT
Model: Setup A
Risk/Reward: 1:2.5
Outcome: SL
Realized R: -1R"""
        res = parse_trade_journal(text)
        self.assertIsNotNone(res)
        self.assertEqual(res["pair"], "XAUUSD")
        self.assertEqual(res["direction"], "SELL")
        self.assertEqual(res["planned_rr"], 2.5)
        self.assertEqual(res["status"], "CLOSED")
        self.assertEqual(res["result"], "SL")
        self.assertEqual(res["actual_r"], -1.0)

    def test_parser_sample_3(self):
        text = """GBPUSD BUY
Model: C1
RR: 1:2
Result: BE
Realized R: 0R"""
        res = parse_trade_journal(text)
        self.assertIsNotNone(res)
        self.assertEqual(res["pair"], "GBPUSD")
        self.assertEqual(res["direction"], "BUY")
        self.assertEqual(res["planned_rr"], 2.0)
        self.assertEqual(res["status"], "CLOSED")
        self.assertEqual(res["result"], "BE")
        self.assertEqual(res["actual_r"], 0.0)

    def test_database_and_stats(self):
        db = Database("/tmp/test_trade_bot.db", Config())
        db.init_db()

        # Insert 3 closed trades
        trade1 = {
            "chat_id": 12345,
            "message_id": 100,
            "pair": "EURUSD",
            "direction": "BUY",
            "model": "C2",
            "planned_rr": 3.0,
            "status": "CLOSED",
            "result": "TP",
            "actual_r": 3.0,
            "before_photo_id": "photo_before_1",
            "after_photo_id": "photo_after_1",
            "notes": "EURUSD trade post",
        }
        tid1 = db.create_trade(trade1)
        db.update_trade_result(tid1, "TP", 3.0, "photo_after_1")

        trade2 = {
            "chat_id": 12345,
            "message_id": 101,
            "pair": "XAUUSD",
            "direction": "SELL",
            "model": "SETUP A",
            "planned_rr": 2.5,
            "status": "CLOSED",
            "result": "SL",
            "actual_r": -1.0,
            "before_photo_id": "photo_before_2",
            "after_photo_id": "photo_after_2",
            "notes": "XAUUSD trade post",
        }
        tid2 = db.create_trade(trade2)
        db.update_trade_result(tid2, "SL", -1.0, "photo_after_2")

        trades = db.get_all_trades()
        stats = compute_statistics(trades)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["net_r"], 2.0)

        # Cleanup
        if os.path.exists("/tmp/test_trade_bot.db"):
            os.remove("/tmp/test_trade_bot.db")

if __name__ == "__main__":
    unittest.main()
