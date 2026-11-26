"""Secret storage, redaction and dashboard password hashing."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# ---------------------------------------------------------------- redaction

_known: set[str] = set()
_lock = threading.Lock()

_PATTERNS = [
    # rtmp(s)://host/app/<stream key>
    (re.compile(r"(rtmps?://[^\s/]+/[^\s/]+/)[^\s'\"]+", re.I), r"\1[REDACTED]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-~+/=]+", re.I), r"\1[REDACTED]"),
    (re.compile(r"((?:access_token|refresh_token|id_token|client_secret|stream_?key|api_?key)[\"']?\s*[=:]\s*[\"']?)[^\s&\"',}]+", re.I),
     r"\1[REDACTED]"),
    (re.compile(r"([?&](?:code|state|key)=)[^\s&\"']+"), r"\1[REDACTED]"),
    (re.compile(r"ya29\.[A-Za-z0-9._\-]+"), "[REDACTED]"),
    (re.compile(r"1//[A-Za-z0-9._\-]{20,}"), "[REDACTED]"),
]


def register_secret(value: str | None) -> None:
    """Remember a secret so it is scrubbed from any later log/diagnostic text."""
    if value and len(value) >= 6:
        with _lock:
            _known.add(value)


def redact(text: str) -> str:
    if not text:
        return text
    with _lock:
        known = sorted(_known, key=len, reverse=True)
    for s in known:
        text = text.replace(s, "[REDACTED]")
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        record.msg = redact(msg)
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(f, RedactingFilter) for h in root.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.handlers = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ---------------------------------------------------------------- encryption

class SecretBox:
    """Fernet encryption with a key file readable only by the service user."""

    def __init__(self, data_dir: Path):
        key_path = data_dir / "secret.key"
        if not key_path.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(Fernet.generate_key())
        os.chmod(key_path, 0o600)
        self._fernet = Fernet(key_path.read_bytes().strip())
        # Separate HMAC key for dashboard session cookies.
        self.hmac_key = hashlib.sha256(b"replay-studio-session" + key_path.read_bytes()).digest()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as e:
            raise ValueError("Stored secret could not be decrypted (secret.key changed?)") from e

    # Signed, expiring session tokens: "<expiry>.<nonce>.<sig>"
    def make_session(self, hours: int, password_version: str) -> str:
        exp = str(int(time.time() + hours * 3600))
        nonce = secrets.token_urlsafe(16)
        sig = self._sign(f"{exp}.{nonce}.{password_version}")
        return f"{exp}.{nonce}.{sig}"

    def check_session(self, token: str | None, password_version: str) -> bool:
        if not token or token.count(".") != 2:
            return False
        exp, nonce, sig = token.split(".")
        if not exp.isdigit() or int(exp) < time.time():
            return False
        return hmac.compare_digest(sig, self._sign(f"{exp}.{nonce}.{password_version}"))

    def _sign(self, msg: str) -> str:
        d = hmac.new(self.hmac_key, msg.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(d).decode().rstrip("=")


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, dk_b64 = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(dk, base64.b64decode(dk_b64))
