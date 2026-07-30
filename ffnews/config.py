import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    NEWS_URL: str = os.getenv(
        "NEWS_URL",
        "https://cdn-nfs.forexfactory.net/ff_calendar_thisweek.json",
    )
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Jakarta")


cfg = Config()
