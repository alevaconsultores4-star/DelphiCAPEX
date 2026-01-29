"""
Authentication utilities for DelphiCAPEX (local JSON users + bcrypt).
"""
from typing import Optional, Dict
import bcrypt
from datetime import datetime
import os

import models
import storage


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt and return the utf-8 decoded hash."""
    if plain is None:
        raise ValueError("Password must be provided")
    hashed = bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
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
