import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"}
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


def _parse_currencies(raw: str) -> List[str]:
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_OWNER_ID: str = os.getenv("BOT_OWNER_ID", "")

    CALENDAR_URL: str = "https://www.forexfactory.com/calendar"
    WATCHED_CURRENCIES: List[str] = field(
        default_factory=lambda: _parse_currencies(
            os.getenv("WATCHED_CURRENCIES", "USD,EUR,GBP,AUD")
        )
    )
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Jakarta")
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    SCRAPE_TIMEOUT_MS: int = int(os.getenv("SCRAPE_TIMEOUT_MS", "30000"))
