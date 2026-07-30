import logging
import os
from dataclasses import dataclass
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


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
