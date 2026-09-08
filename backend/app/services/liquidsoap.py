import logging
import socket
from typing import Optional

from ..config import get_settings

log = logging.getLogger("prodio.liquidsoap")


class LiquidsoapClient:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        settings = get_settings()
        self.host = host or settings.liquidsoap_host
        self.port = port or settings.liquidsoap_port

    def _send(self, command: str, timeout: float = 3.0, full: bool = False) -> str:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                sock.sendall((command.strip() + "\n").encode("utf-8"))
                chunks: list[bytes] = []
                while True:
                    try:
                        data = sock.recv(4096)
                    except socket.timeout:
                        break
                    if not data:
                        break
                    chunks.append(data)
                    joined = b"".join(chunks)
                    if b"END" in joined or b"\r\n" in joined:
                        try:
                            sock.sendall(b"exit\n")
                        except OSError:
                            pass
                        break
                text = b"".join(chunks).decode("utf-8", errors="replace")
                cleaned = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line in ("END", "Bye!"):
                        continue
                    cleaned.append(line)
                if not cleaned:
                    return ""
                return "\n".join(cleaned) if full else cleaned[-1]
        except OSError as exc:
            log.warning("Liquidsoap command failed (%s): %s", command, exc)
            raise

    def ping(self) -> bool:
        try:
            self._send("prodio.status")
            return True
        except OSError:
            return False

    def status(self) -> str:
        try:
            return self._send("prodio.status")
        except OSError:
            return "unavailable"

    def start(self) -> str:
        return self._send("prodio.start")

    def stop(self) -> str:
        return self._send("prodio.stop")

    def reload(self) -> str:
        return self._send("prodio.reload")

    def skip(self) -> str:
        return self._send("prodio.skip")

    def play(self, uri: str) -> str:
        # URI may contain spaces — liquidsoap takes the rest of the line
        return self._send(f"prodio.play {uri}")

    def set_random_mode(self, enabled: bool = True) -> str:
        return self._send("prodio.mode_random" if enabled else "prodio.mode_ordered")

    def current_filename(self) -> Optional[str]:
        """Return path of the currently on-air request, if any."""
        rid = self._send("request.on_air")
        if not rid or not rid.isdigit():
            return None
        meta = self._send(f"request.metadata {rid}", full=True)
        for line in meta.splitlines():
            line = line.strip()
            if line.startswith("filename="):
                return line.split("=", 1)[1].strip().strip('"')
            if line.startswith("initial_uri="):
                raw = line.split("=", 1)[1].strip().strip('"')
                if raw.startswith("annotate:") and ":" in raw[9:]:
                    raw = raw.rsplit(":", 1)[-1]
                return raw
        return None
