"""
Real-time listening event service.
Handles event ingestion, background simulation, in-memory buffering,
streaming statistics computation, and MongoDB persistence.
"""
from __future__ import annotations

import logging
import json
import os
import random
import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

EVENT_TYPES = ["play", "skip", "like", "replay"]
EVENT_WEIGHTS = [0.65, 0.15, 0.12, 0.08]


@dataclass
class ListeningEvent:
    event_id: str
    user_id: str
    song_id: str
    event_type: str
    duration_seconds: int
    timestamp: str
    song_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventService:
    def __init__(
        self,
        max_buffer_size: int = 200,
        mongo_persister: Callable[[dict[str, Any]], None] | None = None,
        stream_input_dir: str | Path | None = None,
    ) -> None:
        self.max_buffer_size = max_buffer_size
        self._buffer: deque[ListeningEvent] = deque(maxlen=max_buffer_size)
        self._total_events_count = 0
        self._active_users: set[str] = set()
        self._song_play_counts: Counter[str] = Counter()
        self._event_type_counts: Counter[str] = Counter()
        self._mongo_persister = mongo_persister
        configured_stream_dir = stream_input_dir if stream_input_dir is not None else os.getenv("STREAM_INPUT_DIR", "streaming/input")
        self._stream_input_dir = Path(configured_stream_dir) if configured_stream_dir else None
        self._lock = threading.Lock()

        # Simulator state
        self._simulator_thread: threading.Thread | None = None
        self._simulator_running = False
        self._sample_users: list[str] = []
        self._sample_items: list[str] = []
        self._song_map_lookup: Callable[[str], str | None] | None = None

    def set_song_lookup(self, lookup_fn: Callable[[str], str | None]) -> None:
        self._song_map_lookup = lookup_fn

    def set_sample_catalog(self, users: list[str], items: list[str]) -> None:
        if users:
            self._sample_users = users[:500]
        if items:
            self._sample_items = items[:1000]

    def record_event(
        self,
        user_id: str,
        song_id: str,
        event_type: str = "play",
        duration_seconds: int = 180,
        song_code: str | None = None,
    ) -> ListeningEvent:
        if event_type not in EVENT_TYPES:
            event_type = "play"

        if song_code is None and self._song_map_lookup:
            song_code = self._song_map_lookup(song_id)

        now_str = datetime.now(timezone.utc).isoformat()
        event = ListeningEvent(
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            user_id=str(user_id),
            song_id=str(song_id),
            event_type=event_type,
            duration_seconds=duration_seconds,
            timestamp=now_str,
            song_code=song_code,
        )

        with self._lock:
            self._buffer.appendleft(event)
            self._total_events_count += 1
            self._active_users.add(str(user_id))
            self._song_play_counts[str(song_id)] += 1
            self._event_type_counts[event_type] += 1

        if self._mongo_persister:
            try:
                self._mongo_persister(event.to_dict())
            except Exception as exc:
                logger.debug("Mongo persister notice: %s", exc)

        self._write_stream_event(event)

        return event

    def _write_stream_event(self, event: ListeningEvent) -> None:
        """Publish API/simulator events to the file source consumed by Spark."""
        if self._stream_input_dir is None:
            return
        try:
            self._stream_input_dir.mkdir(parents=True, exist_ok=True)
            final_path = self._stream_input_dir / f"{event.event_id}.json"
            temporary_path = self._stream_input_dir / f".{event.event_id}.json.tmp"
            temporary_path.write_text(json.dumps(event.to_dict()), encoding="utf-8")
            try:
                temporary_path.replace(final_path)
            except OSError:
                # Some mounted folders do not permit rename; finish the write so
                # the event remains consumable by Spark rather than being lost.
                final_path.write_text(temporary_path.read_text(encoding="utf-8"), encoding="utf-8")
                temporary_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not publish event to Spark input directory: %s", exc)

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in list(self._buffer)[:limit]]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            recent_events = list(self._buffer)
            # Compute top trending songs in the buffer
            recent_song_counts = Counter(e.song_id for e in recent_events)
            top_trending = [
                {
                    "song_id": s_id,
                    "plays": count,
                    "song_code": self._song_map_lookup(s_id) if self._song_map_lookup else None,
                }
                for s_id, count in recent_song_counts.most_common(5)
            ]

            return {
                "total_events_processed": self._total_events_count,
                "buffered_events_count": len(recent_events),
                "unique_active_users": len(self._active_users),
                "event_type_distribution": dict(self._event_type_counts),
                "top_trending_recent_songs": top_trending,
                "simulator_active": self._simulator_running,
                "last_event_timestamp": recent_events[0].timestamp if recent_events else None,
            }

    def start_simulator(self, interval_seconds: float = 2.0) -> bool:
        if not self._sample_users or not self._sample_items:
            raise RuntimeError("The event simulator requires a loaded user and song catalog.")
        with self._lock:
            if self._simulator_running:
                return True
            self._simulator_running = True

        def _run_sim():
            logger.info("Listening event simulator started (interval: %.1fs)", interval_seconds)
            while self._simulator_running:
                try:
                    u_id = random.choice(self._sample_users)
                    s_id = random.choice(self._sample_items)
                    e_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
                    duration = random.randint(30, 240) if e_type != "skip" else random.randint(5, 30)
                    self.record_event(
                        user_id=u_id,
                        song_id=s_id,
                        event_type=e_type,
                        duration_seconds=duration,
                    )
                except Exception as exc:
                    logger.warning("Error in simulator loop: %s", exc)
                time.sleep(interval_seconds)
            logger.info("Listening event simulator stopped")

        self._simulator_thread = threading.Thread(target=_run_sim, daemon=True)
        self._simulator_thread.start()
        return True

    def stop_simulator(self) -> bool:
        with self._lock:
            self._simulator_running = False
        return True
