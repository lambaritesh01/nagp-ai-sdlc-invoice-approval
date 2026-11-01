"""Fixtures for Playwright browser E2E tests.

A real uvicorn server is started in a subprocess against an isolated temp SQLite
database, and a system-installed Chrome is driven via Playwright's channel
mechanism (no bundled-browser download, no TLS bypass).
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Prefer a system browser channel; chromium bundled binary is unavailable here.
_BROWSER_CHANNEL = os.environ.get("E2E_BROWSER_CHANNEL", "chrome")


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """Start the real app on a free port with an isolated DB; yield base URL."""
    port = _free_port()
    db = tmp_path_factory.mktemp("e2e_db") / "invoices.db"
    env = dict(os.environ, INVOICE_DB_PATH=str(db))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            with contextlib.suppress(Exception):
                if httpx.get(base + "/health", timeout=1).status_code == 200:
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError("live server did not become healthy")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


@pytest.fixture(scope="session")
def _playwright():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(_playwright):
    b = _playwright.chromium.launch(channel=_BROWSER_CHANNEL, headless=True)
    yield b
    b.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()
