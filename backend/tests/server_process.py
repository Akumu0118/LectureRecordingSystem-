"""Run an actual API process only against the caller's isolated test schema."""

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from sqlalchemy.engine import make_url

from app.core.config import get_settings


@contextmanager
def live_api(api):
    assert api.schema.startswith("voiceclean_test_") and len(api.schema) == 48
    url = make_url(get_settings().database_url.get_secret_value())
    query = dict(url.query)
    query["options"] = f"-csearch_path={api.schema},public"
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": url.set(query=query).render_as_string(hide_password=False),
        "STORAGE_ROOT": str(api.settings.storage_root),
        "FFPROBE_PATH": api.settings.ffprobe_path,
        "FFMPEG_PATH": api.settings.ffmpeg_path,
    })
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=Path(__file__).resolve().parents[1], env=env, stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
                for _ in range(200):
                    if process.poll() is not None:
                        raise RuntimeError("Isolated API startup failed; private output suppressed")
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.05)
                else:
                    raise RuntimeError("Isolated API startup timed out")
                yield client
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                process.terminate()
            process.wait(timeout=10)
