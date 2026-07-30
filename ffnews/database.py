import sqlite3
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str = "database.db"):
        self.path = path

    def conn(self):
        return sqlite3.connect(self.path)

    def init_db(self):
        with self.conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    event_id TEXT PRIMARY KEY,
                    h2_sent INTEGER DEFAULT 0,
                    h1_sent INTEGER DEFAULT 0,
                    last_checked TEXT
                )
                """
            )
        logger.info("DB initialized")

    def mark_sent(self, event_id: str, which: str):
        with self.conn() as c:
            c.execute("SELECT event_id FROM notifications WHERE event_id=?", (event_id,))
            row = c.fetchone()
            now = datetime.utcnow().isoformat()
            if not row:
                h2 = 1 if which == "h2" else 0
                h1 = 1 if which == "h1" else 0
                c.execute(
                    "INSERT INTO notifications (event_id,h2_sent,h1_sent,last_checked) VALUES (?,?,?,?)",
                    (event_id, h2, h1, now),
                )
            else:
                if which == "h2":
                    c.execute(
                        "UPDATE notifications SET h2_sent=1, last_checked=? WHERE event_id=?",
                        (now, event_id),
                    )
                else:
                    c.execute(
                        "UPDATE notifications SET h1_sent=1, last_checked=? WHERE event_id=?",
                        (now, event_id),
                    )

    def get_status(self, event_id: str) -> Optional[dict]:
        with self.conn() as c:
            c.row_factory = sqlite3.Row
            cur = c.execute("SELECT * FROM notifications WHERE event_id=?", (event_id,))
            r = cur.fetchone()
            return dict(r) if r else None
