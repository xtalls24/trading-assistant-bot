# Forex Factory News Alert Bot (FFNews)

Simple Telegram bot that fetches Forex Factory calendar JSON and sends H-2 and H-1 alerts for High Impact USD and AUD events.

Requirements
- Python 3.12+
- VPS Ubuntu recommended

Install

```bash
git clone <repo>
cd ffnews
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set BOT_TOKEN and BOT_OWNER
```

Run

```bash
python main.py
```

Systemd (example)

Create `/etc/systemd/system/ffnews.service` with:

```
[Unit]
Description=FFNews Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/ffnews
Environment="PATH=/path/to/ffnews/.venv/bin"
ExecStart=/path/to/ffnews/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target

```

Notes
- Bot only notifies High Impact (red) for `USD` and `AUD`.
- Scheduler polls every 5 minutes by default.
- Uses SQLite `ffnews.db` to avoid duplicate notifications.
