import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str, config: Optional[Config] = None):
        self.path = path
        self.config = config or Config()

    def conn(self):
        return sqlite3.connect(self.path)

    def init_db(self):
        with self.conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    pair TEXT,
                    direction TEXT,
                    model TEXT,
                    bias TEXT,
                    poi TEXT,
                    confirmation TEXT,
                    killzone TEXT,
                    result TEXT,
                    rr REAL
                )
                """
            )
        logger.info("Initialized database")

    def add_trade(self, trade: Dict[str, Any]) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO trades (date,pair,direction,model,bias,poi,confirmation,killzone,result,rr) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    trade.get("date"),
                    trade.get("pair"),
                    trade.get("direction"),
                    trade.get("model"),
                    trade.get("bias"),
                    trade.get("poi"),
                    trade.get("confirmation"),
                    trade.get("killzone"),
                    trade.get("result"),
                    trade.get("rr"),
                ),
            )
            return cur.lastrowid

    def get_trade(self, trade_id: int) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            c.row_factory = sqlite3.Row
            cur = c.execute("SELECT * FROM trades WHERE id=?", (trade_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_trade(self, trade_id: int, fields: Dict[str, Any]) -> None:
        keys = ",".join([f"{k}=?" for k in fields.keys()])
        values = list(fields.values()) + [trade_id]
        with self.conn() as c:
            c.execute(f"UPDATE trades SET {keys} WHERE id=?", values)

    def delete_trade(self, trade_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM trades WHERE id=?", (trade_id,))

    def query(self, where: str = "", params: tuple = ()): 
        with self.conn() as c:
            c.row_factory = sqlite3.Row
            cur = c.execute(f"SELECT * FROM trades {where}", params)
            return [dict(r) for r in cur.fetchall()]

    def stats_for_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(rows)
        tp = sum(1 for r in rows if (r.get("result") or "").upper() == "TP")
        sl = sum(1 for r in rows if (r.get("result") or "").upper() == "SL")
        total_r = sum(float(r.get("rr") or 0) for r in rows)
        winrate = (tp / total * 100) if total else 0
        return {"total": total, "tp": tp, "sl": sl, "winrate": round(winrate, 2), "total_r": total_r}

    def trades_in_period(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        with self.conn() as c:
            c.row_factory = sqlite3.Row
            cur = c.execute(
                "SELECT * FROM trades WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date.isoformat(), end_date.isoformat()),
            )
            return [dict(r) for r in cur.fetchall()]
