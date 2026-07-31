import subprocess
import os

repo_dir = "/root/trading-assistant-bot"
os.chdir(repo_dir)

try:
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Add Owner Guard Security and Auto Edit Journal Handler"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("Git push successful!")
except Exception as e:
    print(f"Git commit/push note: {e}")

try:
    subprocess.run(["pm2", "restart", "trading-bot"], check=True)
    print("PM2 restart successful!")
except Exception as e:
    print(f"PM2 restart error: {e}")
