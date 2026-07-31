import os
import sys

# Insert venv site-packages so python3 can import all dependencies
venv_site = "/root/trading-assistant-bot/venv/lib/python3.10/site-packages"
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from main import main

if __name__ == "__main__":
    main()
