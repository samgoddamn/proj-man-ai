"""Lösenordshashning (bcrypt) och JWT-utfärdande/-validering (HS256).

Hemligheten läses från JWT_SECRET. Sätt den i .env i produktion — default-värdet
finns bara för lokal utveckling och loggar en varning vid användning.
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

_DEFAULT_SECRET = "dev-only-change-me"
JWT_SECRET = os.getenv("JWT_SECRET", _DEFAULT_SECRET)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=int(os.getenv("JWT_TTL_HOURS", "24")))

if JWT_SECRET == _DEFAULT_SECRET:
    warnings.warn("JWT_SECRET är inte satt — använder osäker dev-default.", stacklevel=2)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + ACCESS_TOKEN_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    """Returnera user_id ur en giltig token, annars kasta jwt-undantag."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return UUID(payload["sub"])
