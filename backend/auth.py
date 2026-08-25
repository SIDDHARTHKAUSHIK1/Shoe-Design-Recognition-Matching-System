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
    if not username or not password:
        return None
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username.strip(),))
            row = cursor.fetchone()
            if row:
                user = dict(row)
                if verify_password(password, user["password_hash"]):
                    try:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now, user["user_id"]))
                        conn.commit()
                    except Exception:
                        pass
                    
                    user.pop("password_hash", None)
                    return user
    except Exception as e:
        logger.warning(f"Authentication error for '{username}': {e}")

    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user info by user_id."""
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, role, full_name, is_active, must_change_password, created_at, last_login FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Error fetching user by id {user_id}: {e}")
        return None


def list_users() -> list:
    """List all users in the system."""
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT user_id, username, role, full_name, plain_password, is_active, must_change_password, created_at, last_login FROM users ORDER BY user_id ASC")
            except sqlite3.OperationalError:
                cursor.execute("SELECT user_id, username, role, full_name, is_active, must_change_password, created_at, last_login FROM users ORDER BY user_id ASC")
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"Error listing users: {e}")
        return []


def change_user_password(user_id: int, old_password: str, new_password: str) -> bool:
    """Change user password after verifying old password, and reset must_change_password flag."""
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row or not verify_password(old_password, row["password_hash"]):
                return False
                
            new_hash = hash_password(new_password)
            try:
                cursor.execute("UPDATE users SET password_hash = ?, plain_password = ?, must_change_password = 0 WHERE user_id = ?", (new_hash, new_password, user_id))
            except sqlite3.OperationalError:
                cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE user_id = ?", (new_hash, user_id))
            conn.commit()
            return True
    except Exception:
        return False


def create_user(username: str, password: str, role: str, full_name: str) -> Optional[int]:
    """Create a new user account."""
    pwd_hash = hash_password(password)
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, plain_password, role, full_name)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, pwd_hash, password, role, full_name))
            except sqlite3.OperationalError:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, full_name)
                    VALUES (?, ?, ?, ?)
                """, (username, pwd_hash, role, full_name))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.warning(f"Error creating user {username}: {e}")
        return None


def update_user(user_id: int, role: Optional[str] = None, full_name: Optional[str] = None, is_active: Optional[int] = None, password: Optional[str] = None) -> bool:
    """Update user properties or reset password."""
    try:
        from backend.database import get_db_connection
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
                try:
                    cursor.execute("UPDATE users SET plain_password = ? WHERE user_id = ?", (password, user_id))
                except sqlite3.OperationalError:
                    pass
                
            if not updates:
                return False
                
            params.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", tuple(params))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.warning(f"Error updating user {user_id}: {e}")
        return False


def delete_user(user_id: int) -> bool:
    """Delete a user account by user_id."""
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.warning(f"Error deleting user {user_id}: {e}")
        return False


def seed_initial_users() -> Dict[str, str]:
    """
    Ensure admin and employee accounts exist securely.
    """
    import os
    admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")
    emp_pwd = os.getenv("EMPLOYEE_PASSWORD", "emp123")
    
    try:
        from backend.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Seed or check Admin
            cursor.execute("SELECT user_id FROM users WHERE username = 'admin'")
            admin_row = cursor.fetchone()
            if not admin_row:
                try:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, plain_password, role, full_name, must_change_password) VALUES ('admin', ?, ?, 'admin', 'Admin', 0)",
                        (hash_password(admin_pwd), admin_pwd)
                    )
                except sqlite3.OperationalError:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role, full_name) VALUES ('admin', ?, 'admin', 'Admin')",
                        (hash_password(admin_pwd),)
                    )
            else:
                try:
                    cursor.execute("UPDATE users SET password_hash = ?, plain_password = ? WHERE username = 'admin'", (hash_password(admin_pwd), admin_pwd))
                except sqlite3.OperationalError:
                    cursor.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (hash_password(admin_pwd),))

            # Seed or check Employee
            cursor.execute("SELECT user_id FROM users WHERE username = 'employee'")
            emp_row = cursor.fetchone()
            if not emp_row:
                try:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, plain_password, role, full_name, must_change_password) VALUES ('employee', ?, ?, 'employee', 'Inventory Specialist', 0)",
                        (hash_password(emp_pwd), emp_pwd)
                    )
                except sqlite3.OperationalError:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role, full_name) VALUES ('employee', ?, 'employee', 'Inventory Specialist')",
                        (hash_password(emp_pwd),)
                    )
            else:
                try:
                    cursor.execute("UPDATE users SET password_hash = ?, plain_password = ? WHERE username = 'employee'", (hash_password(emp_pwd), emp_pwd))
                except sqlite3.OperationalError:
                    cursor.execute("UPDATE users SET password_hash = ? WHERE username = 'employee'", (hash_password(emp_pwd),))

            conn.commit()
    except Exception as e:
        logger.warning(f"Initial user seeding notice: {e}")
    return {"admin": admin_pwd, "employee": emp_pwd}

