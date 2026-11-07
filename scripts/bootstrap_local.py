"""Create local credentials; prints one-time randomly generated passwords."""
from __future__ import annotations

from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import password_hash  # noqa: E402


root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    raise SystemExit(".env exists; refusing to overwrite existing secrets.")
admin = secrets.token_urlsafe(15)
test = secrets.token_urlsafe(15)
lines = [
    "# LOCAL ONLY – never commit or share this file",
    f"ADMIN_PASSWORD_HASH='{password_hash(admin)}'",
    f"TEST_PASSWORD_HASH='{password_hash(test)}'",
    f"SESSION_SECRET='{secrets.token_urlsafe(48)}'",
    "MODEL_PROVIDER=mock",
    "OPENROUTER_API_KEY=",
    "OPENROUTER_MODEL=",
    "APP_ENV=development",
    "MAX_IMAGES_PER_SESSION=20",
    "MAX_UPLOAD_MB=10",
    "SESSION_TTL_MINUTES=60",
    "",
]
path.write_text("\n".join(lines), encoding="utf-8")
try:
    path.chmod(0o600)
except OSError:
    pass
print("Local .env was created. Save these passwords now (they will not be shown again):")
print(f"  Admin login: admin    Password: {admin}")
print(f"  Test login:  test     Password: {test}")
print("WARNING: Do not commit .env or paste passwords in a public issue.")
