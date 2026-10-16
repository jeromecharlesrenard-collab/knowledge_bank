"""Tests for the preview server (no window is opened)."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools.preview import start_server


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
