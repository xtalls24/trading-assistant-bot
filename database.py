import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: Optional[str] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.path = path or self.config.DB_PATH

    def conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.conn() as c:
            # 1. Main Trades Table
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_code TEXT UNIQUE,
                    chat_id INTEGER,
                    message_id INTEGER,
                    bot_reply_message_id INTEGER,
                    created_at TEXT,
                    date TEXT,
                    pair TEXT,
                    direction TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    risk_input TEXT,
                    planned_rr REAL,
                    notes TEXT,
                    before_photo_id TEXT,
                    after_photo_id TEXT,
                    status TEXT DEFAULT 'OPEN',
                    result TEXT,
                    actual_r REAL,
                    closed_at TEXT,
                    model TEXT,
                    bias TEXT,
                    poi TEXT,
                    confirmation TEXT,
                    killzone TEXT,
                    rr REAL
                )
                """
            )

            # Alter table migration to ensure all columns exist if db existed previously
            existing_cols = [
                r["name"] for r in c.execute("PRAGMA table_info(trades)").fetchall()
            ]
            columns_to_add = {
                "trade_code": "TEXT",
                "chat_id": "INTEGER",
                "message_id": "INTEGER",
                "bot_reply_message_id": "INTEGER",
                "created_at": "TEXT",
                "entry_price": "REAL",
                "stop_loss": "REAL",
                "take_profit": "REAL",
                "risk_input": "TEXT",
                "planned_rr": "REAL",
                "notes": "TEXT",
                "before_photo_id": "TEXT",
                "after_photo_id": "TEXT",
                "status": "TEXT DEFAULT 'OPEN'",
                "actual_r": "REAL",
                "closed_at": "TEXT",
                "model": "TEXT",
                "bias": "TEXT",
                "poi": "TEXT",
                "confirmation": "TEXT",
                "killzone": "TEXT",
                "rr": "REAL",
            }
            for col, dtype in columns_to_add.items():
                if col not in existing_cols:
                    try:
                        c.execute(f"ALTER TABLE trades ADD COLUMN {col} {dtype}")
                    except Exception as e:
                        logger.warning(f"Could not add column {col}: {e}")

            # 2. Message Mappings (Telegram thread reply tracking)
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS message_mappings (
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    trade_id INTEGER NOT NULL,
                    PRIMARY KEY (chat_id, message_id),
                    FOREIGN KEY (trade_id) REFERENCES trades (id) ON DELETE CASCADE
                )
                """
            )

            # 3. Economic Calendar Cache Table
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS news_events (
                    event_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    impact TEXT DEFAULT 'high',
                    event_timestamp INTEGER NOT NULL,
                    forecast TEXT,
                    previous TEXT,
                    actual TEXT,
                    scraped_at TEXT NOT NULL
                )
                """
            )

            # Migration check for news_events table
            existing_news_cols = [
                r["name"] for r in c.execute("PRAGMA table_info(news_events)").fetchall()
            ]
            if "actual" not in existing_news_cols:
                try:
                    c.execute("ALTER TABLE news_events ADD COLUMN actual TEXT")
                except Exception as e:
                    logger.warning(f"Could not add column actual to news_events: {e}")

            # 4. News Reminders Sent Table (Deduplication)
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    reminder_type TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    UNIQUE(event_id, reminder_type)
                )
                """
            )
        logger.info("Initialized database with unified schema")

    # --- Trade Repository Methods ---

    def create_trade(self, trade_data: Dict[str, Any]) -> int:
        with self.conn() as c:
            cur = c.execute(
                """
                INSERT INTO trades (
                    trade_code, chat_id, message_id, bot_reply_message_id,
                    created_at, date, pair, direction, entry_price, stop_loss,
                    take_profit, risk_input, planned_rr, notes, before_photo_id,
                    status, model, bias, poi, confirmation, killzone, rr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_data.get("trade_code"),
                    trade_data.get("chat_id"),
                    trade_data.get("message_id"),
                    trade_data.get("bot_reply_message_id"),
                    trade_data.get("created_at") or datetime.now().isoformat(),
                    trade_data.get("date") or date.today().isoformat(),
                    trade_data.get("pair"),
                    trade_data.get("direction"),
                    trade_data.get("entry_price"),
                    trade_data.get("stop_loss"),
                    trade_data.get("take_profit"),
                    trade_data.get("risk_input"),
                    trade_data.get("planned_rr"),
                    trade_data.get("notes"),
                    trade_data.get("before_photo_id"),
                    trade_data.get("status", "OPEN"),
                    trade_data.get("model"),
                    trade_data.get("bias"),
                    trade_data.get("poi"),
                    trade_data.get("confirmation"),
                    trade_data.get("killzone"),
                    trade_data.get("planned_rr") or trade_data.get("rr"),
                ),
            )
            trade_id = cur.lastrowid

            # Auto-assign trade_code if missing
            if not trade_data.get("trade_code"):
                trade_code = f"#TRADE-{trade_id}"
                c.execute(
                    "UPDATE trades SET trade_code=? WHERE id=?", (trade_code, trade_id)
                )

            # Add message mapping for original post & reply
            chat_id = trade_data.get("chat_id")
            if chat_id:
                if trade_data.get("message_id"):
                    c.execute(
                        "INSERT OR REPLACE INTO message_mappings (chat_id, message_id, trade_id) VALUES (?,?,?)",
                        (chat_id, trade_data.get("message_id"), trade_id),
                    )
                if trade_data.get("bot_reply_message_id"):
                    c.execute(
                        "INSERT OR REPLACE INTO message_mappings (chat_id, message_id, trade_id) VALUES (?,?,?)",
                        (chat_id, trade_data.get("bot_reply_message_id"), trade_id),
                    )

            return trade_id

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute("SELECT * FROM trades WHERE id=?", (trade_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_trade_by_code(self, trade_code: str) -> Optional[Dict[str, Any]]:
        code = trade_code.strip()
        if not code.startswith("#"):
            code = f"#{code}"
        raw_id = code.replace("#TRADE-", "").replace("#", "")
        with self.conn() as c:
            cur = c.execute(
                "SELECT * FROM trades WHERE trade_code=? OR trade_code=? OR id=?",
                (code, code.upper(), raw_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_trade_by_message(
        self, chat_id: int, message_id: int
    ) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute(
                """
                SELECT t.* FROM trades t
                JOIN message_mappings m ON t.id = m.trade_id
                WHERE m.chat_id = ? AND m.message_id = ?
                """,
                (chat_id, message_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def update_trade_result(
        self,
        trade_id: int,
        result: str,
        actual_r: float,
        after_photo_id: Optional[str] = None,
    ) -> None:
        closed_at = datetime.now().isoformat()
        with self.conn() as c:
            if after_photo_id:
                c.execute(
                    """
                    UPDATE trades
                    SET status='CLOSED', result=?, actual_r=?, after_photo_id=?, closed_at=?, rr=?
                    WHERE id=?
                    """,
                    (result, actual_r, after_photo_id, closed_at, actual_r, trade_id),
                )
            else:
                c.execute(
                    """
                    UPDATE trades
                    SET status='CLOSED', result=?, actual_r=?, closed_at=?, rr=?
                    WHERE id=?
                    """,
                    (result, actual_r, closed_at, actual_r, trade_id),
                )

    def delete_trade(self, trade_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM trades WHERE id=?", (trade_id,))
            c.execute("DELETE FROM message_mappings WHERE trade_id=?", (trade_id,))

    def get_all_trades(self) -> List[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute("SELECT * FROM trades ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_open_trades(self) -> List[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_latest_open_trade(
        self, chat_id: int, pair: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            if pair and pair != "UNKNOWN":
                cur = c.execute(
                    """
                    SELECT * FROM trades
                    WHERE chat_id = ? AND pair = ? AND status = 'OPEN'
                    ORDER BY id DESC LIMIT 1
                    """,
                    (chat_id, pair),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

            cur = c.execute(
                """
                SELECT * FROM trades
                WHERE chat_id = ? AND status = 'OPEN'
                ORDER BY id DESC LIMIT 1
                """,
                (chat_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def trades_in_period(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        with self.conn() as c:
            cur = c.execute(
                "SELECT * FROM trades WHERE date BETWEEN ? AND ? ORDER BY date ASC, id ASC",
                (start_date.isoformat(), end_date.isoformat()),
            )
            return [dict(r) for r in cur.fetchall()]

    # --- News Events Cache Methods ---

    def save_news_events(self, events: List[Dict[str, Any]]) -> None:
        now_str = datetime.now().isoformat()
        with self.conn() as c:
            for e in events:
                ts = e.get("timestamp_utc") or e.get("event_timestamp") or 0
                c.execute(
                    """
                    INSERT OR REPLACE INTO news_events
                    (event_id, title, currency, impact, event_timestamp, forecast, previous, actual, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        e.get("event_id"),
                        e.get("title"),
                        e.get("currency"),
                        e.get("impact", "high"),
                        ts,
                        e.get("forecast"),
                        e.get("previous"),
                        e.get("actual"),
                        now_str,
                    ),
                )

    def get_news_events(
        self, min_timestamp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        with self.conn() as c:
            if min_timestamp:
                cur = c.execute(
                    "SELECT * FROM news_events WHERE event_timestamp >= ? ORDER BY event_timestamp ASC",
                    (min_timestamp,),
                )
            else:
                cur = c.execute(
                    "SELECT * FROM news_events ORDER BY event_timestamp ASC"
                )
            rows = [dict(r) for r in cur.fetchall()]
            # Normalize dictionary keys so both timestamp_utc and event_timestamp are present
            for r in rows:
                r["timestamp_utc"] = r.get("event_timestamp", 0)
            return rows

    # --- Notifications Tracking Methods ---

    def is_notification_sent(self, event_id: str, reminder_type: str) -> bool:
        with self.conn() as c:
            cur = c.execute(
                "SELECT id FROM sent_notifications WHERE event_id=? AND reminder_type=?",
                (event_id, reminder_type),
            )
            return cur.fetchone() is not None

    def mark_notification_sent(self, event_id: str, reminder_type: str) -> None:
        now_str = datetime.now().isoformat()
        with self.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO sent_notifications (event_id, reminder_type, sent_at) VALUES (?, ?, ?)",
                (event_id, reminder_type, now_str),
            )
