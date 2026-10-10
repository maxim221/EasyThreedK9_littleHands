#!/usr/bin/env python3
"""Owner-only local control socket for the Little Hands GUI.

The socket thread never touches Tk objects. Requests are handed to the GUI
through its existing event queue and are executed on the Tk main thread.
"""

from __future__ import annotations

import json
import hashlib
import os
import secrets
import socket
import stat
import threading
from pathlib import Path
from typing import Callable


PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 64 * 1024


def default_socket_path(project_root: Path) -> Path:
    digest = hashlib.sha256(str(project_root.resolve()).encode("utf-8")).hexdigest()[:12]
    runtime_value = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    runtime_dir = Path(runtime_value) if runtime_value else Path("/tmp") / f"little-hands-{os.getuid()}"
    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if runtime_dir.stat().st_uid != os.getuid():
        raise RuntimeError(f"Little Hands runtime directory is not owned by the current user: {runtime_dir}")
    try:
        os.chmod(runtime_dir, 0o700)
    except OSError:
        pass
    return runtime_dir / f"lh-{digest}.sock"


def load_or_create_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        token = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        token = secrets.token_hex(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(token + "\n")
    if len(token) != 64 or any(ch not in "0123456789abcdef" for ch in token):
        raise RuntimeError(f"invalid Little Hands control token: {path}")
    os.chmod(path, 0o600)
    return token


class LocalControlServer:
    def __init__(
        self,
        socket_path: Path,
        token_path: Path,
        dispatch: Callable[[dict[str, object]], dict[str, object]],
    ) -> None:
        self.socket_path = socket_path
        self.token = load_or_create_token(token_path)
        self.dispatch = dispatch
        self._stop = threading.Event()
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        if self.socket_path.exists() or self.socket_path.is_socket():
            mode = self.socket_path.lstat().st_mode
            if not stat.S_ISSOCK(mode):
                raise RuntimeError(f"control socket path is not a socket: {self.socket_path}")
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.settimeout(0.2)
                probe.connect(str(self.socket_path))
            except OSError:
                pass
            else:
                raise RuntimeError("another Little Hands control server is already running")
            finally:
                probe.close()
            self.socket_path.unlink()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        listener.listen(4)
        listener.settimeout(0.5)
        self._listener = listener
        self._thread = threading.Thread(target=self._serve, name="little-hands-control", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        try:
            if self.socket_path.is_socket():
                self.socket_path.unlink()
        except OSError:
            pass

    def _serve(self) -> None:
        while not self._stop.is_set():
            listener = self._listener
            if listener is None:
                break
            try:
                conn, _address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(15.0)
                response = self._handle_connection(conn)
                try:
                    conn.sendall(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
                except OSError:
                    pass

    def _handle_connection(self, conn: socket.socket) -> dict[str, object]:
        data = bytearray()
        try:
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_REQUEST_BYTES:
                    return {"ok": False, "error": "request too large"}
            request = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": f"invalid request: {exc}"}
        if not isinstance(request, dict):
            return {"ok": False, "error": "request must be a JSON object"}
        if not secrets.compare_digest(str(request.get("token") or ""), self.token):
            return {"ok": False, "error": "authentication failed"}
        if request.get("version") != PROTOCOL_VERSION:
            return {"ok": False, "error": "unsupported protocol version"}
        try:
            return self.dispatch(request)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
