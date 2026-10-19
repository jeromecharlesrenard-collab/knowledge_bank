"""Tests for the preview server (no window is opened)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools.preview import SITE_ID, find_running, serve_until_idle, start_server


@pytest.fixture
def server_url(mini_site: Path):
    server = start_server(mini_site, 0, attempts=1)
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


def test_serves_home_page_without_cache(server_url: str) -> None:
    with urllib.request.urlopen(server_url) as resp:
        assert resp.status == 200
        assert resp.headers["Cache-Control"] == "no-store"
        assert b"JCR Knowledge Bank" in resp.read()


def test_wrong_case_returns_404_like_github(server_url: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(server_url + "alpha.html")
    assert err.value.code == 404


def test_find_running_recognizes_own_server(server_url: str) -> None:
    port = int(server_url.rstrip("/").rsplit(":", 1)[1])
    assert find_running(port, attempts=1) == f"http://localhost:{port}/"
    with urllib.request.urlopen(server_url) as resp:
        assert resp.headers["X-Preview-Site"] == SITE_ID


def test_server_stops_when_idle(mini_site: Path) -> None:
    server = start_server(mini_site, 0, attempts=1)
    port = server.server_address[1]
    started = time.monotonic()
    serve_until_idle(server, idle_seconds=0.3, poll=0.05)
    assert time.monotonic() - started < 5
    assert find_running(port, attempts=1) is None
