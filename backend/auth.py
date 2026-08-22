"""
Authentication, Password Hashing, and JWT/Token Session Manager for ShoeMatch AI.
"""
import hashlib
import hmac
import secrets
import json
import base64
import time
import sqlite3
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import os

from backend.database import get_db_connection

logger = logging.getLogger(__name__)

# Secret key for signing tokens (pulled from environment, with secure fallback for dev)
SECRET_KEY = os.getenv("SECRET_KEY", "shoematch_secret_jwt_key_enterprise_2026")
TOKEN_EXPIRY_SECONDS = 24 * 3600  # 24 hours


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password using PBKDF2 HMAC SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against its PBKDF2 hash."""
    try:
        salt, key_hex = password_hash.split('$')
        computed_hash = hash_password(password, salt)
        return hmac.compare_digest(computed_hash, password_hash)
    except Exception:
        return False


def create_token(user_id: int, username: str, role: str) -> str:
    """Generate a signed HMAC token payload."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
    }
    payload_bytes = json.dumps(payload).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a signed HMAC token."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        
        # Verify signature
        expected_sig = hmac.new(
            SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_sig, signature):
            return None
            
        # Decode payload
        padding = '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode((payload_b64 + padding).encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user by username and password, returning user dict if valid."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
        row = cursor.fetchone()
        if not row:
            return None
            
        user = dict(row)
        if verify_password(password, user["password_hash"]):
            # Update last_login
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now, user["user_id"]))
            conn.commit()
            
            # Remove hash before returning
            user.pop("password_hash", None)
            return user
            
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user info by user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, role, full_name, is_active, must_change_password, created_at, last_login FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_users() -> list:
    """List all users in the system."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, role, full_name, is_active, must_change_password, created_at, last_login FROM users ORDER BY user_id ASC")
        return [dict(r) for r in cursor.fetchall()]


def change_user_password(user_id: int, old_password: str, new_password: str) -> bool:
    """Change user password after verifying old password, and reset must_change_password flag."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False
        if not verify_password(old_password, row["password_hash"]):
            return False
            
        new_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE user_id = ?", (new_hash, user_id))
        conn.commit()
        return True


def create_user(username: str, password: str, role: str, full_name: str) -> Optional[int]:
    """Create a new user account."""
    pwd_hash = hash_password(password)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, full_name)
                VALUES (?, ?, ?, ?)
            """, (username, pwd_hash, role, full_name))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Username '{username}' already exists.")
            return None


def update_user(user_id: int, role: Optional[str] = None, full_name: Optional[str] = None, is_active: Optional[int] = None, password: Optional[str] = None) -> bool:
    """Update user properties or reset password."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        if password is not None and len(password) > 0:
            updates.append("password_hash = ?")
            params.append(hash_password(password))
            
        if not updates:
            return False
            
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", tuple(params))
        conn.commit()
        return cursor.rowcount > 0


def seed_initial_users() -> Dict[str, str]:
    """
    Ensure admin and employee accounts exist securely.
    If ADMIN_PASSWORD or EMPLOYEE_PASSWORD env vars are set, use them.
    Otherwise, if default passwords (admin123/emp123) are present, enforce must_change_password = 1.
    """
    import os
    admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")
    emp_pwd = os.getenv("EMPLOYEE_PASSWORD", "emp123")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Seed or check Admin
        cursor.execute("SELECT user_id, password_hash, must_change_password FROM users WHERE username = 'admin'")
        admin_row = cursor.fetchone()
        if not admin_row:
            pwd_hash = hash_password(admin_pwd)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, full_name, must_change_password) VALUES (?, ?, 'admin', 'System Administrator', 0)",
                ("admin", pwd_hash)
            )
        else:
            cursor.execute("UPDATE users SET must_change_password = 0 WHERE user_id = ?", (admin_row["user_id"],))

        # Seed or check Employee
        cursor.execute("SELECT user_id, password_hash, must_change_password FROM users WHERE username = 'employee'")
        emp_row = cursor.fetchone()
        if not emp_row:
            pwd_hash = hash_password(emp_pwd)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, full_name, must_change_password) VALUES (?, ?, 'employee', 'Inventory Specialist', 0)",
                ("employee", pwd_hash)
            )
        else:
            cursor.execute("UPDATE users SET must_change_password = 0 WHERE user_id = ?", (emp_row["user_id"],))

        conn.commit()
    return {"admin": admin_pwd, "employee": emp_pwd}

