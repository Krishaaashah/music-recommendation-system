#!/usr/bin/env python3
"""
Event Producer Script
Generates continuous, realistic listening interaction events (play, skip, like, replay)
using real User IDs and Song Item IDs from the dataset and posts them to FastAPI / MongoDB.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import time
import urllib.request
import uuid
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

EVENT_TYPES = ["play", "skip", "like", "replay"]
EVENT_WEIGHTS = [0.65, 0.15, 0.12, 0.08]


def post_event(api_url: str, event_data: dict) -> bool:
    try:
        req = urllib.request.Request(
            f"{api_url.rstrip('/')}/events",
            data=json.dumps(event_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status in (200, 201)
    except Exception as exc:
        logger.warning("Could not post event to %s: %s", api_url, exc)
        return False


def load_ids(mapping_path: Path) -> list[str]:
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
    values: list[str] = []
    with mapping_path.open("r", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) >= 2 and row[1].strip():
                values.append(row[1].strip())
    if not values:
        raise ValueError(f"Mapping file contains no IDs: {mapping_path}")
    return values


def write_event(input_dir: Path, event_data: dict) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    event_id = event_data["event_id"]
    temporary_path = input_dir / f".{event_id}.json.tmp"
    final_path = input_dir / f"{event_id}.json"
    temporary_path.write_text(json.dumps(event_data), encoding="utf-8")
    temporary_path.replace(final_path)
    return final_path


def main():
    parser = argparse.ArgumentParser(description="Real-Time Music Event Producer")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000")
    parser.add_argument(
        "--user-mapping",
        type=Path,
        default=Path(os.getenv("USER_MAPPING_PATH", "dataset/user_mapping.csv")),
    )
    parser.add_argument(
        "--song-mapping",
        type=Path,
        default=Path(os.getenv("SONG_MAPPING_PATH", "dataset/song_mapping.csv")),
    )
    parser.add_argument("--input-dir", type=Path, default=Path("streaming/input"), help="JSON event directory for Spark")
    parser.add_argument("--skip-api", action="store_true", help="Only write event files; do not call FastAPI")
    parser.add_argument("--rate", type=float, default=1.0, help="Events per second")
    parser.add_argument("--count", type=int, default=0, help="Total events to send (0 = infinite)")
    args = parser.parse_args()

    try:
        user_ids = load_ids(args.user_mapping)
        song_ids = load_ids(args.song_mapping)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    logger.info(
        "Starting Event Producer -> %s (Rate: %.1f ev/s, users=%d, songs=%d)",
        args.api_url,
        args.rate,
        len(user_ids),
        len(song_ids),
    )
    delay = 1.0 / max(args.rate, 0.1)

    sent = 0
    try:
        while True:
            u_id = random.choice(user_ids)
            s_id = random.choice(song_ids)
            e_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
            dur = random.randint(30, 240) if e_type != "skip" else random.randint(5, 30)

            payload = {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "user_id": u_id,
                "song_id": s_id,
                "event_type": e_type,
                "duration_seconds": dur,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            path = write_event(args.input_dir, payload)
            success = True if args.skip_api else post_event(args.api_url, payload)
            sent += 1
            logger.info(
                "[%d] %s User %s -> Song %s (%s, %ds)",
                sent,
                "Wrote" if args.skip_api else ("Wrote/posted" if success else "Wrote; API unavailable:"),
                u_id,
                s_id,
                e_type,
                dur,
            )

            if args.count > 0 and sent >= args.count:
                break

            time.sleep(delay)
    except KeyboardInterrupt:
        logger.info("Event Producer stopped by user. Total sent: %d", sent)


if __name__ == "__main__":
    main()
