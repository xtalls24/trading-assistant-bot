# Telegram Trading Assistant Bot (Python)

Minimal Telegram bot to record trading journal and show statistics. Designed for a single user and runs locally.

Requirements
- Python 3.12+
- Install dependencies:

```bash
pip install -r requirements.txt
```

Setup
1. Copy `.env.example` to `.env` and set your `BOT_TOKEN`.
2. Run the bot:

```bash
python main.py
```

Commands
- `/add` - Tambah trade jurnal langkah demi langkah.
- `/weekly` - Statistik 7 hari terakhir.
- `/monthly` - Statistik bulan berjalan.
- `/pair EURUSD` - Statistik per pair.
- `/model C1` - Statistik per model.
- `/today` - Tampilkan trade hari ini.
- `/delete <id>` - Hapus trade berdasarkan ID.
- `/edit <id>` - Mulai proses edit (lihat output bot).

Notes
- Data disimpan di `database.db` (SQLite).
- Logging diaktifkan.
