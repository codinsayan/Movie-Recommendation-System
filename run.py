"""One-command launcher: `python run.py` starts the server and opens the browser."""
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

HOST, PORT = "127.0.0.1", 8000

if __name__ == "__main__":
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    uvicorn.run("app:app", host=HOST, port=PORT, reload="--reload" in sys.argv, app_dir="backend")
