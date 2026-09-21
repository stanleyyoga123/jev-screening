"""Run the local API and frontend together on macOS/Linux."""

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from types import FrameType


ROOT = Path(__file__).resolve().parents[1]


def interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def stop_servers(processes: list[subprocess.Popen]) -> None:
    # npm and Uvicorn's reloader create children; signal their whole groups.
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start FastAPI on localhost:8000 and Vite on localhost:5173. Ctrl+C stops both.",
        epilog="Activate your project environment first, or set PYTHON_BIN to its Python executable.",
    )
    parser.parse_args()
    npm = shutil.which("npm")
    if npm is None:
        print("npm is missing. Install Node.js 22.18+ first.", file=sys.stderr)
        return 1
    if importlib.util.find_spec("uvicorn") is None:
        print(f"Uvicorn is missing from {sys.executable}. Activate your project environment and install apps/api/requirements.txt.", file=sys.stderr)
        return 1
    if not (ROOT / "apps/web/node_modules/.bin/vite").exists():
        print("Frontend dependencies are missing. Run: npm --prefix apps/web ci", file=sys.stderr)
        return 1
    for port in (8000, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                print(f"Cannot use port {port}: {exc}. Stop the existing server before running this launcher.", file=sys.stderr)
                return 1

    signal.signal(signal.SIGTERM, interrupt)
    commands = [
        ("API", [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"], ROOT / "apps/api"),
        ("Frontend", [npm, "run", "dev"], ROOT / "apps/web"),
    ]
    processes: list[subprocess.Popen] = []
    print(f"Python: {sys.executable}\nFrontend: http://127.0.0.1:5173\nAPI docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both servers.\n", flush=True)
    try:
        for _, command, directory in commands:
            processes.append(subprocess.Popen(command, cwd=directory, start_new_session=True))
        while True:
            for (name, _, _), process in zip(commands, processes):
                status = process.poll()
                if status is not None:
                    print(f"\n{name} exited ({status}); stopping the other server.", flush=True)
                    return status if status > 0 else 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping API and frontend…", flush=True)
        return 0
    finally:
        # A second Ctrl+C must not interrupt child-process cleanup.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_servers(processes)


if __name__ == "__main__":
    raise SystemExit(main())
