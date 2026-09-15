"""Local correction memory and a small trained text-classification fallback."""

import collections
import hashlib
import math
import os
import re
import sqlite3
from contextlib import contextmanager

import pandas as pd

from security import DataCipher


def normalize_text(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


class CorrectionStore:
    def __init__(self, db_path=None, cipher=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.environ.get(
            "CARBON_LEARNING_PATH", os.path.join(project_root, "data", "carbon_learning.db")
        )
        self.cipher = cipher or DataCipher()
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS user_corrections (
                    user_id TEXT NOT NULL,
                    phrase_hash TEXT NOT NULL,
                    encrypted_phrase TEXT NOT NULL,
                    label TEXT NOT NULL,
                    quantity REAL,
                    unit TEXT,
                    uses INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, phrase_hash)
                )
            """)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, user_id, phrase, label, quantity=None, unit=None):
        normalized = normalize_text(phrase)
        if not normalized or not label:
            raise ValueError("Correction requires source text and a label")
        phrase_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO user_corrections VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, phrase_hash) DO UPDATE SET
                    label=excluded.label, quantity=excluded.quantity, unit=excluded.unit,
                    uses=user_corrections.uses+1, updated_at=CURRENT_TIMESTAMP
            """, (user_id, phrase_hash, self.cipher.encrypt(normalized), label, quantity, unit))
        return {"phrase_hash": phrase_hash, "label": label, "quantity": quantity, "unit": unit}

    def lookup(self, user_id, phrase):
        if not user_id:
            return None
        phrase_hash = hashlib.sha256(normalize_text(phrase).encode("utf-8")).hexdigest()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT label, quantity, unit, uses FROM user_corrections WHERE user_id = ? AND phrase_hash = ?",
                (user_id, phrase_hash),
            ).fetchone()
        return dict(row) if row else None


class NaiveBayesActivityClassifier:
    """Multinomial Naive Bayes trained from the repository phrase dataset."""

    def __init__(self, dataset_path=None):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dataset_path = dataset_path or os.path.join(
            project_root, "data", "Daily_Activity_Text_Dataset.csv"
        )
        frame = pd.read_csv(dataset_path)
        self.label_counts = collections.Counter(frame["activity_label"])
        self.token_counts = {label: collections.Counter() for label in self.label_counts}
        self.total_tokens = collections.Counter()
        self.vocabulary = set()
        for _, row in frame.iterrows():
            label = row["activity_label"]
            tokens = self._tokens(row["text"])
            self.token_counts[label].update(tokens)
            self.total_tokens[label] += len(tokens)
            self.vocabulary.update(tokens)
        self.document_count = len(frame)

    def predict(self, text):
        tokens = self._tokens(text)
        if not tokens:
            return None
        vocabulary_size = max(1, len(self.vocabulary))
        scores = {}
        for label, count in self.label_counts.items():
            score = math.log(count / self.document_count)
            denominator = self.total_tokens[label] + vocabulary_size
            for token in tokens:
                score += math.log((self.token_counts[label][token] + 1) / denominator)
            scores[label] = score
        maximum = max(scores.values())
        probabilities = {label: math.exp(score - maximum) for label, score in scores.items()}
        total = sum(probabilities.values())
        label = max(probabilities, key=probabilities.get)
        return {"label": label, "confidence": probabilities[label] / total,
                "model": "multinomial-naive-bayes-v1"}

    @staticmethod
    def _tokens(text):
        return [token for token in re.findall(r"[a-z]+", str(text).lower())
                if token not in {"i", "a", "the", "for", "to", "today", "my"}]
