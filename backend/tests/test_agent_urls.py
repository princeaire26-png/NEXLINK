from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nexlink_agent.urls import http_base, websocket_base


@pytest.mark.parametrize(
    ("address", "expected_http", "expected_websocket"),
    [
        (
            "192.168.1.20:8000",
            "http://192.168.1.20:8000",
            "ws://192.168.1.20:8000/ws",
        ),
        (
            "https://nexlink.example.com/control/",
            "https://nexlink.example.com/control",
            "wss://nexlink.example.com/control/ws",
        ),
        (
            "wss://nexlink.example.com/ws",
            "https://nexlink.example.com",
            "wss://nexlink.example.com/ws",
        ),
    ],
)
def test_server_address_normalization(address, expected_http, expected_websocket):
    assert http_base(address) == expected_http
    assert websocket_base(address) == expected_websocket


@pytest.mark.parametrize(
    "address",
    [
        "",
        "ftp://nexlink.example.com",
        "https://user:password@nexlink.example.com",
        "http://nexlink.example.com:bad",
    ],
)
def test_rejects_invalid_server_addresses(address):
    with pytest.raises(ValueError):
        http_base(address)
