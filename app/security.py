"""Credentials, brute-force protection and isolated in-memory sessions."""
from __future__ import annotations

import base64
from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import hmac
import secrets
import time


# Scrypt salt and output are base64url-encoded; hash format is stable for setup script.
def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    enc = lambda raw: base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"scrypt${enc(salt)}${enc(digest)}"


def valid_password_hash(stored: str) -> bool:
    parts = stored.split('$')
    if len(parts) != 3 or parts[0] != 'scrypt':
        return False
    try:
        salt, digest = (base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
                        for value in parts[1:])
    except ValueError:
        return False
    return len(salt) == 16 and len(digest) == 64


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, known = stored.split("$")
        if algorithm != "scrypt":
            return False
        padding = lambda value: value + "=" * (-len(value) % 4)
        raw_salt = base64.urlsafe_b64decode(padding(salt))
        raw_digest = base64.urlsafe_b64decode(padding(known))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=raw_salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, raw_digest)
    except (ValueError, TypeError, MemoryError):
        return False


@dataclass
class Session:
    token: str
    csrf: str
    role: str
    created_at: float
    batches: dict = field(default_factory=dict)
    live_calls: dict = field(default_factory=lambda: dict(sent=0, succeeded=0, failed=0, repeated=0))


class WorkspaceStore:
    def __init__(self, ttl_minutes: int, *, now=time.time) -> None:
        self.ttl_seconds = ttl_minutes * 60
        self.now = now
        self.sessions: dict[str, Session] = {}
        self.login_attempts: dict[str, list[float]] = defaultdict(list)
        self.global_login_attempts: list[float] = []

    def cleanup(self) -> None:
        now = self.now()
        for token, session in list(self.sessions.items()):
            if now - session.created_at > self.ttl_seconds:
                del self.sessions[token]
        for ip, attempts in list(self.login_attempts.items()):
            active = [t for t in attempts if now - t < 60]
            if active:
                self.login_attempts[ip] = active
            else:
                del self.login_attempts[ip]

    def is_rate_limited(self, ip: str) -> bool:
        self.cleanup()
        self.global_login_attempts = [t for t in self.global_login_attempts if self.now() - t < 60]
        if len(self.global_login_attempts) >= 40 or len(self.login_attempts.get(ip, [])) >= 8:
            return True
        self.global_login_attempts.append(self.now())
        return False

    def record_login_attempt(self, ip: str) -> None:
        self.login_attempts[ip].append(self.now())

    def start(self, role: str) -> Session:
        self.cleanup()
        token = secrets.token_urlsafe(32)
        session = Session(token, secrets.token_urlsafe(32), role, self.now())
        self.sessions[token] = session
        return session

    def get(self, token: str | None) -> Session | None:
        self.cleanup()
        return self.sessions.get(token or "")

    def end(self, token: str | None) -> None:
        self.sessions.pop(token or "", None)
