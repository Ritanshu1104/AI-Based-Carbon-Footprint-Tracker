"""Encrypted, per-user local journal, goals, trends, and forecasting inputs."""

import datetime as dt
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

from security import DataCipher


class JournalRepository:
    def __init__(self, db_path=None, cipher=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.environ.get(
            "CARBON_JOURNAL_PATH", os.path.join(project_root, "data", "carbon_journal.db")
        )
        self.cipher = cipher or DataCipher()
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
                CREATE TABLE IF NOT EXISTS secure_journal_entries (
                    entry_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    encrypted_text TEXT NOT NULL,
                    total_co2_kg REAL NOT NULL,
                    low_co2_kg REAL NOT NULL,
                    high_co2_kg REAL NOT NULL,
                    confidence TEXT NOT NULL,
                    encrypted_result TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS journal_user_date
                    ON secure_journal_entries(user_id, entry_date DESC);
                CREATE TABLE IF NOT EXISTS monthly_goals (
                    user_id TEXT NOT NULL,
                    month TEXT NOT NULL,
                    target_kg REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, month)
                );
            """)

    def save(self, user_id, original_text, result, entry_date=None):
        entry_date = self._date(entry_date)
        entry_id = str(uuid.uuid4())
        created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        interval = result["total_co2_range_kg"]
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO secure_journal_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id, user_id, entry_date, created_at, self.cipher.encrypt(original_text),
                result["total_co2_kg"], interval["low"], interval["high"], result["confidence"],
                self.cipher.encrypt(json.dumps(result, ensure_ascii=False)),
            ))
        return self.get(user_id, entry_id)

    def get(self, user_id, entry_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM secure_journal_entries WHERE entry_id = ? AND user_id = ?",
                (entry_id, user_id),
            ).fetchone()
        return self._row(row) if row else None

    def list(self, user_id, limit=30, month=None):
        limit = max(1, min(int(limit), 365))
        parameters = [user_id]
        where = "user_id = ?"
        if month:
            self._month(month)
            where += " AND substr(entry_date, 1, 7) = ?"
            parameters.append(month)
        parameters.append(limit)
        with self._connection() as connection:
            rows = connection.execute(f"""
                SELECT * FROM secure_journal_entries WHERE {where}
                ORDER BY entry_date DESC, created_at DESC LIMIT ?
            """, parameters).fetchall()
        return [self._row(row) for row in rows]

    def delete(self, user_id, entry_id):
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM secure_journal_entries WHERE entry_id = ? AND user_id = ?",
                (entry_id, user_id),
            )
        return cursor.rowcount > 0

    def set_goal(self, user_id, month, target_kg):
        month = self._month(month)
        target_kg = float(target_kg)
        if target_kg <= 0:
            raise ValueError("Goal must be greater than zero")
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO monthly_goals VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, month) DO UPDATE SET
                    target_kg = excluded.target_kg, updated_at = excluded.updated_at
            """, (user_id, month, target_kg, dt.datetime.now(dt.timezone.utc).isoformat()))
        return {"month": month, "target_kg": target_kg}

    def get_goal(self, user_id, month):
        month = self._month(month)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT month, target_kg FROM monthly_goals WHERE user_id = ? AND month = ?",
                (user_id, month),
            ).fetchone()
        return dict(row) if row else None

    def dashboard(self, user_id, month):
        month = self._month(month)
        entries = self.list(user_id, limit=365, month=month)
        categories = {}
        daily = {}
        for entry in entries:
            daily[entry["entry_date"]] = daily.get(entry["entry_date"], 0.0) + entry["total_co2_kg"]
            for item in entry["result"].get("breakdown", []):
                category = item.get("category", "Other")
                categories[category] = categories.get(category, 0.0) + float(item.get("co2_kg", 0))
        total = sum(daily.values())
        goal = self.get_goal(user_id, month)
        return {
            "month": month, "entry_count": len(entries), "total_co2_kg": round(total, 3),
            "daily": [{"date": date, "co2_kg": round(value, 3)} for date, value in sorted(daily.items())],
            "categories": [{"category": key, "co2_kg": round(value, 3)}
                           for key, value in sorted(categories.items(), key=lambda pair: -pair[1])],
            "goal": goal,
            "goal_progress_percent": round(total / goal["target_kg"] * 100, 1) if goal else None,
            "series": [daily[key] for key in sorted(daily)],
        }

    def _row(self, row):
        return {
            "entry_id": row["entry_id"], "entry_date": row["entry_date"],
            "created_at": row["created_at"],
            "original_text": self.cipher.decrypt(row["encrypted_text"]),
            "total_co2_kg": row["total_co2_kg"],
            "total_co2_range_kg": {"low": row["low_co2_kg"], "high": row["high_co2_kg"]},
            "confidence": row["confidence"],
            "result": json.loads(self.cipher.decrypt(row["encrypted_result"])),
        }

    @staticmethod
    def _date(value):
        value = value or dt.date.today().isoformat()
        try:
            return dt.date.fromisoformat(value).isoformat()
        except (TypeError, ValueError) as error:
            raise ValueError("entry_date must use YYYY-MM-DD format") from error

    @staticmethod
    def _month(value):
        try:
            return dt.datetime.strptime(str(value), "%Y-%m").strftime("%Y-%m")
        except ValueError as error:
            raise ValueError("month must use YYYY-MM format") from error
