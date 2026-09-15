"""Local multi-user authentication and authenticated encryption at rest."""

import base64
import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken


class DataCipher:
    """Encrypt journal payloads with a local key excluded from version control."""

    def __init__(self, key_path=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.key_path = key_path or os.environ.get(
            "CARBON_KEY_PATH", os.path.join(project_root, "data", ".carbon.key")
        )
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self):
        environment_key = os.environ.get("CARBON_MASTER_KEY")
        if environment_key:
            return environment_key.encode("ascii")
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as handle:
                return handle.read().strip()
        key = Fernet.generate_key()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(self.key_path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(key)
        return key

    def encrypt(self, value):
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token):
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise ValueError("Stored record could not be decrypted with the active key") from error


class AuthRepository:
    USERNAME = re.compile(r"^[a-zA-Z0-9_.-]{3,40}$")
    PBKDF2_ITERATIONS = 600_000

    def __init__(self, db_path=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.environ.get(
            "CARBON_AUTH_PATH", os.path.join(project_root, "data", "carbon_accounts.db")
        )
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
            """)

    def register(self, username, password):
        username = str(username or "").strip()
        if not self.USERNAME.fullmatch(username):
            raise ValueError("Username must be 3–40 characters using letters, numbers, dot, dash, or underscore")
        if not isinstance(password, str) or len(password) < 10:
            raise ValueError("Password must contain at least 10 characters")
        salt = secrets.token_bytes(16)
        password_hash = self._derive(password, salt)
        user_id = str(uuid.uuid4())
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, password_hash, base64.b64encode(salt).decode("ascii"),
                     dt.datetime.now(dt.timezone.utc).isoformat()),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("Username already exists") from error
        return self._public_user(user_id, username)

    def login(self, username, password, hours=12):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (str(username or "").strip(),)
            ).fetchone()
        if row is None:
            raise ValueError("Invalid username or password")
        salt = base64.b64decode(row["salt"])
        if not hmac.compare_digest(row["password_hash"], self._derive(str(password or ""), salt)):
            raise ValueError("Invalid username or password")
        token = secrets.token_urlsafe(32)
        now = dt.datetime.now(dt.timezone.utc)
        expires = now + dt.timedelta(hours=hours)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO auth_tokens VALUES (?, ?, ?, ?)",
                (self._token_hash(token), row["user_id"], expires.isoformat(), now.isoformat()),
            )
        return {"token": token, "expires_at": expires.isoformat(),
                "user": self._public_user(row["user_id"], row["username"])}

    def resolve_token(self, token):
        if not token:
            return None
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (now,))
            row = connection.execute("""
                SELECT users.user_id, users.username FROM auth_tokens
                JOIN users ON users.user_id = auth_tokens.user_id
                WHERE auth_tokens.token_hash = ? AND auth_tokens.expires_at > ?
            """, (self._token_hash(token), now)).fetchone()
        return self._public_user(row["user_id"], row["username"]) if row else None

    def logout(self, token):
        with self._connection() as connection:
            connection.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (self._token_hash(token),))

    @classmethod
    def _derive(cls, password, salt):
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, cls.PBKDF2_ITERATIONS
        ).hex()

    @staticmethod
    def _token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_user(user_id, username):
        return {"user_id": user_id, "username": username}
