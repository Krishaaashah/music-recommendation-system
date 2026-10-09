from __future__ import annotations

import logging
import os
from typing import Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, PyMongoError

logger = logging.getLogger(__name__)

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "music_recommendation"


class MongoService:
    """Service for storing and querying recommendation data and interaction logs in MongoDB."""

    def __init__(self, uri: str | None = None, db_name: str | None = None) -> None:
        self.uri = uri or os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
        self.db_name = db_name or os.getenv("MONGO_DB_NAME", DEFAULT_DB_NAME)
        self._client: MongoClient[dict[str, Any]] | None = None

    @property
    def client(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            self._client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
            )
        return self._client

    @property
    def db(self):
        return self.client[self.db_name]

    def is_available(self) -> bool:
        """Check if MongoDB server is reachable."""
        try:
            self.client.admin.command("ping")
            return True
        except (ConnectionFailure, PyMongoError, Exception):
            return False

    def ensure_indexes(self) -> None:
        """Ensure necessary indexes exist for performance."""
        try:
            self.db.recommendations.create_index([("user_id", ASCENDING)], unique=True)
            self.db.songs.create_index([("item_id", ASCENDING)], unique=True)
            self.db.events.create_index([("user_id", ASCENDING)])
            self.db.events.create_index([("timestamp", ASCENDING)])
            self.db.user_profiles.create_index([("user_id", ASCENDING)], unique=True)
        except Exception as exc:
            logger.warning("Could not create MongoDB indexes: %s", exc)

    def get_recommendations(self, user_id: str, limit: int = 10) -> list[dict[str, Any]] | None:
        """Fetch recommendation document for a specific user."""
        try:
            doc = self.db.recommendations.find_one({"user_id": str(user_id)}, {"_id": 0})
            if not doc or "recommendations" not in doc:
                return None
            items = doc["recommendations"]
            return items[:limit]
        except Exception as exc:
            logger.warning("Error querying MongoDB recommendations for user %s: %s", user_id, exc)
            return None

    def save_recommendations(self, user_id: str, recommendations: list[dict[str, Any]]) -> bool:
        """Upsert recommendation document for a user."""
        try:
            self.db.recommendations.update_one(
                {"user_id": str(user_id)},
                {"$set": {"user_id": str(user_id), "recommendations": recommendations, "count": len(recommendations)}},
                upsert=True,
            )
            return True
        except Exception as exc:
            logger.warning("Error saving recommendations to MongoDB for user %s: %s", user_id, exc)
            return False

    def save_song_mapping(self, item_id: str, song_code: str) -> bool:
        """Store item_id to MSD song_code mapping."""
        try:
            self.db.songs.update_one(
                {"item_id": str(item_id)},
                {"$set": {"item_id": str(item_id), "song_code": song_code}},
                upsert=True,
            )
            return True
        except Exception as exc:
            logger.warning("Error saving song mapping to MongoDB: %s", exc)
            return False

    def get_song_mapping(self, item_id: str) -> str | None:
        """Retrieve MSD song_code for an item_id."""
        try:
            doc = self.db.songs.find_one({"item_id": str(item_id)}, {"_id": 0, "song_code": 1})
            return doc.get("song_code") if doc else None
        except Exception:
            return None

    def log_interaction(self, user_id: str, item_id: str, action: str = "listen") -> bool:
        """Log a real-time listening interaction event."""
        import datetime
        try:
            event = {
                "user_id": str(user_id),
                "item_id": str(item_id),
                "action": action,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
            self.db.events.insert_one(event)
            return True
        except Exception as exc:
            logger.warning("Error logging interaction to MongoDB: %s", exc)
            return False

    def get_recent_interactions(self, user_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent interaction logs."""
        try:
            query = {"user_id": str(user_id)} if user_id else {}
            cursor = self.db.events.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception:
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get document counts and status from MongoDB."""
        try:
            if not self.is_available():
                return {
                    "status": "offline",
                    "database": self.db_name,
                    "recommendations_count": 0,
                    "songs_count": 0,
                    "events_count": 0,
                }
            return {
                "status": "connected",
                "database": self.db_name,
                "recommendations_count": self.db.recommendations.count_documents({}),
                "songs_count": self.db.songs.count_documents({}),
                "events_count": self.db.events.count_documents({}),
            }
        except Exception as exc:
            return {
                "status": f"error: {exc}",
                "database": self.db_name,
                "recommendations_count": 0,
                "songs_count": 0,
                "events_count": 0,
            }
