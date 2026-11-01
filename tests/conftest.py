"""Shared fixtures for invoice approval tests. Isolated temp DB per test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    """A TestClient backed by a fresh SQLite file under tmp_path."""
    db = tmp_path / "invoices.db"
    app = create_app(db_path=str(db))
    with TestClient(app) as c:
        yield c
