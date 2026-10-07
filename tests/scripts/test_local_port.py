from __future__ import annotations

import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

ROOT = Path(__file__).resolve().parents[2]
PORT_HELPER = ROOT / "scripts" / "local_port.sh"


def test_detects_an_existing_loopback_listener() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; local_loopback_port_is_free "$2"',
                "test-local-port",
                str(PORT_HELPER),
                str(port),
            ],
            capture_output=True,
            check=False,
            text=True,
        )

    assert result.returncode == 1, (
        f"a loopback listener on port {port} must be reported occupied; "
        f"helper exit={result.returncode}, stderr={result.stderr!r}"
    )


def test_accepts_a_free_loopback_port() -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; local_loopback_port_is_free "$2"',
            "test-local-port",
            str(PORT_HELPER),
            str(port),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, (
        f"a free loopback port {port} must be accepted; "
        f"helper exit={result.returncode}, stderr={result.stderr!r}"
    )


@pytest.mark.parametrize(("status", "expected_exit"), [(200, 0), (404, 1)])
def test_http_health_probe_requires_a_success_status(
    status: int, expected_exit: int
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(self.server.health_status)  # type: ignore[attr-defined]
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.health_status = status  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; local_loopback_http_health_ok "$2"',
                "test-local-port",
                str(PORT_HELPER),
                str(port),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert result.returncode == expected_exit, (
        f"HTTP /health status {status} must yield helper exit {expected_exit}; "
        f"actual={result.returncode}, stderr={result.stderr!r}"
    )
