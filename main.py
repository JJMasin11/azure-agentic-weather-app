"""
main.py — Unified launcher for the Azure Agentic Weather App.

Usage:
    python main.py

Starts the MCP server, Agent backend, and Streamlit frontend as subprocesses,
waits for all three to be healthy, then prints the URL. Press Ctrl-C to exit;
all servers are terminated cleanly on exit.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ── Configuration ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
load_dotenv(dotenv_path=ROOT / ".env")

MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "8501"))

MCP_HEALTH_URL = f"http://localhost:{MCP_PORT}/health"
AGENT_HEALTH_URL = f"http://localhost:{AGENT_PORT}/health"
AGENT_CHAT_URL = f"http://localhost:{AGENT_PORT}/chat"
FRONTEND_HEALTH_URL = f"http://localhost:{FRONTEND_PORT}/_stcore/health"


# ── Health polling ─────────────────────────────────────────────────────────────

def _wait_for_health(url: str, timeout: int, label: str) -> bool:
    """Poll GET url until status 200 or timeout (seconds). Returns True on success."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ── Graceful shutdown ──────────────────────────────────────────────────────────

def _shutdown(procs: list, log_files: list) -> None:
    """SIGTERM all processes, wait up to 5 s each, then SIGKILL stragglers."""
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    for f in log_files:
        f.close()

# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    log_files = []
    procs = []

    try:
        # Open log files
        mcp_log = open(ROOT / "mcp_server.log", "w")
        agent_log = open(ROOT / "agent_server.log", "w")
        log_files = [mcp_log, agent_log]

        # ── Banner ─────────────────────────────────────────────────────────────
        print(
            "╔══════════════════════════════════════╗\n"
            "║   Azure Agentic Weather App          ║\n"
            f"║   MCP      → http://localhost:{MCP_PORT}   ║\n"
            f"║   Agent    → http://localhost:{AGENT_PORT}   ║\n"
            f"║   Frontend → http://localhost:{FRONTEND_PORT} ║\n"
            "║   Logs  → mcp_server.log             ║\n"
            "║           agent_server.log           ║\n"
            "║           frontend.log               ║\n"
            "╚══════════════════════════════════════╝"
        )

        # ── Start MCP server ───────────────────────────────────────────────────
        print("Starting MCP server...", end="  ", flush=True)
        mcp_proc = subprocess.Popen(
            [sys.executable, "mcp_server.py"],
            cwd=ROOT / "mcp-server",
            stdout=mcp_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(mcp_proc)

        if not _wait_for_health(MCP_HEALTH_URL, timeout=30, label="MCP"):
            print("FAILED")
            print(
                f"Error: MCP server did not become healthy within 30 s.\n"
                f"Check mcp_server.log for details.",
                file=sys.stderr,
            )
            _shutdown(procs, log_files)
            sys.exit(1)
        print("OK")

        # ── Start Agent server ─────────────────────────────────────────────────
        print("Starting Agent server...", end=" ", flush=True)
        agent_proc = subprocess.Popen(
            [sys.executable, "agent_server.py"],
            cwd=ROOT / "agent-backend",
            stdout=agent_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(agent_proc)

        if not _wait_for_health(AGENT_HEALTH_URL, timeout=15, label="Agent"):
            print("FAILED")
            print(
                f"Error: Agent server did not become healthy within 15 s.\n"
                f"Check agent_server.log for details.",
                file=sys.stderr,
            )
            _shutdown(procs, log_files)
            sys.exit(1)
        print("OK")

        # ── Start Streamlit frontend ───────────────────────────────────────────
        print("Starting Streamlit frontend...", end=" ", flush=True)
        frontend_log = open(ROOT / "frontend.log", "w")
        log_files.append(frontend_log)
        frontend_proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "frontend/app.py",
             "--server.port", str(FRONTEND_PORT),
             "--server.headless", "true"],
            cwd=ROOT,
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(frontend_proc)

        if not _wait_for_health(FRONTEND_HEALTH_URL, timeout=30, label="Frontend"):
            print("FAILED")
            print(
                f"Error: Streamlit frontend did not become healthy within 30 s.\n"
                f"Check frontend.log for details.",
                file=sys.stderr,
            )
            _shutdown(procs, log_files)
            sys.exit(1)
        print("OK\n")

        print(f"Open your browser at: http://localhost:{FRONTEND_PORT}")
        print("Press Ctrl-C to stop all services.\n")

        # Keep the launcher alive until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print()

    finally:
        print("Shutting down...")
        _shutdown(procs, log_files)


if __name__ == "__main__":
    main()
