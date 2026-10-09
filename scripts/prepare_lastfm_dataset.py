"""Prepare the Last.fm 1K event log for Mahout and the application.

The source file contains one event per line. This command streams the file,
aggregates repeated user/track listens, and writes a compact application-ready
catalog without loading the 2.5 GB source file into memory.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import defaultdict
from pathlib import Path


def _track_key(track_mbid: str, artist_mbid: str, artist_name: str, track_name: str) -> str:
    if track_mbid:
        return f"mbid:{track_mbid.lower()}"
    return f"name:{artist_mbid.lower()}:{artist_name.casefold()}:{track_name.casefold()}"


def _flush_batch(
    connection: sqlite3.Connection,
    counts: dict[tuple[str, str], int],
    metadata: dict[str, tuple[str, str, str, str]],
) -> None:
    if not counts:
        return
    connection.executemany(
        """
        INSERT INTO interactions(user_key, track_key, play_count)
        VALUES (?, ?, ?)
        ON CONFLICT(user_key, track_key) DO UPDATE SET play_count = play_count + excluded.play_count
        """,
        ((user, track, count) for (user, track), count in counts.items()),
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO tracks(track_key, artist_mbid, artist_name, track_mbid, track_name)
        VALUES (?, ?, ?, ?, ?)
        """,
        ((track, artist_mbid, artist_name, track_mbid, track_name)
         for track, (artist_mbid, artist_name, track_mbid, track_name) in metadata.items()),
    )
    connection.commit()
    counts.clear()
    metadata.clear()


def prepare_lastfm_dataset(
    input_file: Path,
    profile_file: Path,
    output_dir: Path,
    batch_size: int = 100_000,
) -> tuple[int, int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_file = output_dir / ".lastfm_aggregate.sqlite3"
    if sqlite_file.exists():
        sqlite_file.unlink()

    connection = sqlite3.connect(sqlite_file)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.executescript(
            """
            CREATE TABLE interactions(
                user_key TEXT NOT NULL,
                track_key TEXT NOT NULL,
                play_count INTEGER NOT NULL,
                PRIMARY KEY(user_key, track_key)
            ) WITHOUT ROWID;
            CREATE TABLE tracks(
                track_key TEXT PRIMARY KEY,
                artist_mbid TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                track_mbid TEXT NOT NULL,
                track_name TEXT NOT NULL
            ) WITHOUT ROWID;
            """
        )

        batch_counts: dict[tuple[str, str], int] = defaultdict(int)
        batch_metadata: dict[str, tuple[str, str, str, str]] = {}
        raw_rows = 0
        skipped_rows = 0

        with input_file.open("r", encoding="utf-8", errors="replace") as source:
            for line in source:
                raw_rows += 1
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) < 6:
                    skipped_rows += 1
                    continue

                user_key = fields[0].strip()
                artist_mbid = fields[2].strip()
                artist_name = fields[3].strip()
                track_mbid = fields[4].strip()
                track_name = fields[5].strip()
                if not user_key or not track_name:
                    skipped_rows += 1
                    continue

                track_key = _track_key(track_mbid, artist_mbid, artist_name, track_name)
                batch_counts[(user_key, track_key)] += 1
                batch_metadata.setdefault(
                    track_key,
                    (artist_mbid, artist_name, track_mbid, track_name),
                )

                if len(batch_counts) >= batch_size:
                    _flush_batch(connection, batch_counts, batch_metadata)
                    if raw_rows % 1_000_000 < batch_size:
                        print(f"Processed {raw_rows:,} raw events...")

        _flush_batch(connection, batch_counts, batch_metadata)
        connection.execute("CREATE INDEX interactions_track_idx ON interactions(track_key)")
        connection.commit()

        users = {
            row[0]: index
            for index, row in enumerate(
                connection.execute("SELECT user_key FROM interactions ORDER BY user_key"),
                start=1,
            )
        }
        tracks = {
            row[0]: index
            for index, row in enumerate(
                connection.execute("SELECT track_key FROM tracks ORDER BY track_key"),
                start=1,
            )
        }

        user_mapping = output_dir / "user_mapping.csv"
        song_mapping = output_dir / "song_mapping.csv"
        interactions_file = output_dir / "train_triplets.txt"
        mahout_file = output_dir / "mahout_input.csv"
        metadata_file = output_dir / "song_metadata.csv"

        with user_mapping.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows((user, user_id) for user, user_id in users.items())

        with song_mapping.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows((track, track_id) for track, track_id in tracks.items())

        with interactions_file.open("w", encoding="utf-8") as raw_handle, mahout_file.open(
            "w", encoding="utf-8", newline=""
        ) as mahout_handle:
            mahout_writer = csv.writer(mahout_handle)
            cursor = connection.execute(
                "SELECT user_key, track_key, play_count FROM interactions ORDER BY user_key, track_key"
            )
            for user, track, count in cursor:
                raw_handle.write(f"{user}\t{track}\t{count}\n")
                mahout_writer.writerow([users[user], tracks[track], count])

        with metadata_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "item_id",
                    "track_key",
                    "artist_name",
                    "track_name",
                    "artist_mbid",
                    "track_mbid",
                    "total_plays",
                    "unique_listeners",
                ]
            )
            for track, item_id in tracks.items():
                artist_mbid, artist_name, track_mbid, track_name = connection.execute(
                    "SELECT artist_mbid, artist_name, track_mbid, track_name FROM tracks WHERE track_key = ?",
                    (track,),
                ).fetchone()
                total_plays, unique_listeners = connection.execute(
                    "SELECT SUM(play_count), COUNT(*) FROM interactions WHERE track_key = ?",
                    (track,),
                ).fetchone()
                writer.writerow(
                    [
                        item_id,
                        track,
                        artist_name,
                        track_name,
                        artist_mbid,
                        track_mbid,
                        total_plays or 0,
                        unique_listeners or 0,
                    ]
                )

        with profile_file.open("r", encoding="utf-8", errors="replace") as source, (
            output_dir / "user_profiles.tsv"
        ).open("w", encoding="utf-8") as target:
            target.write("user_id\tgender\tage\tcountry\tsignup\n")
            for line in source:
                target.write(line)

        print(
            f"Finished: {raw_rows:,} raw events, {raw_rows - skipped_rows:,} valid events, "
            f"{len(users):,} users, {len(tracks):,} tracks"
        )
        return raw_rows, len(users), len(tracks)
    finally:
        connection.close()
        if sqlite_file.exists():
            sqlite_file.unlink()
        wal_file = sqlite_file.with_name(sqlite_file.name + "-wal")
        shm_file = sqlite_file.with_name(sqlite_file.name + "-shm")
        for temporary_file in (wal_file, shm_file):
            if temporary_file.exists():
                temporary_file.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare Last.fm 1K data for Mahout and the API.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("dataset/lastfm-dataset-1K/userid-timestamp-artid-artname-traid-traname.tsv"),
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("dataset/lastfm-dataset-1K/userid-profile.tsv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("dataset/lastfm"))
    args = parser.parse_args()
    prepare_lastfm_dataset(args.input, args.profiles, args.output_dir)
