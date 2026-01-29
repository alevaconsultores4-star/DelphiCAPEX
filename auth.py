"""
Authentication utilities for DelphiCAPEX (local JSON users + bcrypt).
"""
from typing import Optional, Dict
from datetime import datetime
import os
import hashlib
import base64
from typing import Tuple

import models
import storage
 

# Try to import bcrypt; fall back to PBKDF2 if bcrypt not available
_USE_BCRYPT = True
try:
    import bcrypt  # type: ignore
except Exception:
    _USE_BCRYPT = False
    print("Warning: bcrypt not available, falling back to PBKDF2 (insecure compared to bcrypt). Install bcrypt for stronger hashing.")

# PBKDF2 parameters (used when bcrypt unavailable)
_ITERATIONS = 200_000
_SALT_BYTES = 16
__HASH_NAME = "sha256"


def hash_password(plain: str) -> str:
    """Hash a plaintext password and return a string representation.

    Uses bcrypt when available, otherwise PBKDF2-HMAC-SHA256 as a fallback.
    """
    if plain is None:
        raise ValueError("Password must be provided")
    if _USE_BCRYPT:
        hashed = bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt())
        return hashed.decode('utf-8')
    # PBKDF2 fallback: store as iterations$salt$b64hash
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode('utf-8'), salt, _ITERATIONS)
    return f"{_ITERATIONS}${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(dk).decode('utf-8')}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash (bcrypt or PBKDF2)."""
    if not hashed:
        return False
    if _USE_BCRYPT:
        try:
            return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    # PBKDF2 fallback parsing: iterations$salt$b64hash
    try:
        iterations_str, salt_b64, hash_b64 = hashed.split('$')
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode('utf-8'), salt, iterations)
        return hashlib.compare_digest(dk, expected)
    except Exception:
        return False


def authenticate(email: str, password: str) -> Optional[models.User]:
    """Authenticate user by email/password. Returns User or None."""
    user_rec = storage.get_user_by_email(email)
    if not user_rec:
        return None
    if verify_password(password, user_rec.get('password_hash', '')):
        return models.User.from_dict(user_rec)
    return None


def seed_admin(email: str = "delphi@delphi.local", password: str = "ChangeMe123!"):
    """
    Create an initial Delphi admin user if none exists.
    NOTE: Call from a secure environment and change the password immediately.
    """
    existing = storage.get_user_by_email(email)
    if existing:
        return models.User.from_dict(existing)

    user = models.User(
        email=email,
        password_hash=hash_password(password),
        role="delphi_admin",
        client_id=None,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    storage.create_user(user.to_dict())
    return user
