"""
Batch ingestion script to load Apache Mahout recommendation output and song mappings into MongoDB.
Satisfies the NoSQL/MongoDB rubric requirement for unstructured/semi-structured data conversion and querying.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient, UpdateOne

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.recommendation_service import parse_recommendation_lines

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mongo_importer")


def import_recommendations_to_mongo(
    mahout_path: Path,
    mongo_uri: str = "mongodb://localhost:27017",
    db_name: str = "music_recommendation",
    batch_size: int = 5000,
) -> int:
    """Import Mahout recommendation part files into MongoDB."""
    if not mahout_path.exists():
        logger.error(f"Mahout path does not exist: {mahout_path}")
        return 0

    client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    db = client[db_name]
    coll = db.recommendations

    files = [mahout_path] if mahout_path.is_file() else sorted(mahout_path.rglob("*"))
    files = [
        f for f in files
        if f.is_file() and not f.name.startswith((".", "_")) and not f.name.endswith(".crc")
    ]

    if not files:
        logger.error(f"No candidate files found at {mahout_path}")
        return 0

    total_inserted = 0
    ops: list[UpdateOne] = []

    for file_path in files:
        logger.info(f"Reading recommendations from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            for user_id, items in parse_recommendation_lines(f):
                if not items:
                    continue
                rec_list = [{"item_id": item.item_id, "score": item.score} for item in items]
                doc = {
                    "user_id": str(user_id),
                    "count": len(rec_list),
                    "recommendations": rec_list,
                }
                ops.append(
                    UpdateOne(
                        {"user_id": str(user_id)},
                        {"$set": doc},
                        upsert=True,
                    )
                )

                if len(ops) >= batch_size:
                    result = coll.bulk_write(ops, ordered=False)
                    total_inserted += result.upserted_count + result.modified_count + result.matched_count
                    ops.clear()
                    logger.info(f"Imported {total_inserted} user recommendations...")

    if ops:
        result = coll.bulk_write(ops, ordered=False)
        total_inserted += result.upserted_count + result.modified_count + result.matched_count
        ops.clear()

    # Create index
    coll.create_index("user_id", unique=True)
    logger.info(f"Finished importing {total_inserted} user recommendations into MongoDB.")
    return total_inserted


def import_song_mappings_to_mongo(
    mapping_path: Path,
    mongo_uri: str = "mongodb://localhost:27017",
    db_name: str = "music_recommendation",
    batch_size: int = 10000,
) -> int:
    """Import item_id -> song_code mappings into MongoDB."""
    if not mapping_path.exists():
        logger.warning(f"Song mapping path does not exist: {mapping_path}")
        return 0

    client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    db = client[db_name]
    coll = db.songs

    total_inserted = 0
    ops: list[UpdateOne] = []

    logger.info(f"Reading song mappings from {mapping_path}")
    with open(mapping_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            song_code, item_id = row[0].strip(), row[1].strip()
            ops.append(
                UpdateOne(
                    {"item_id": str(item_id)},
                    {"$set": {"item_id": str(item_id), "song_code": song_code}},
                    upsert=True,
                )
            )

            if len(ops) >= batch_size:
                result = coll.bulk_write(ops, ordered=False)
                total_inserted += result.upserted_count + result.modified_count + result.matched_count
                ops.clear()
                logger.info(f"Imported {total_inserted} song mappings...")

    if ops:
        result = coll.bulk_write(ops, ordered=False)
        total_inserted += result.upserted_count + result.modified_count + result.matched_count
        ops.clear()

    coll.create_index("item_id", unique=True)
    logger.info(f"Finished importing {total_inserted} song mappings into MongoDB.")
    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Mahout recommendation data into MongoDB.")
    parser.add_argument(
        "--mahout-path",
        type=Path,
        default=Path(os.getenv("MAHOUT_RECOMMENDATIONS_PATH", root_dir / "output" / "mahout")),
        help="Path to Mahout output file or directory",
    )
    parser.add_argument(
        "--song-mapping",
        type=Path,
        default=Path(os.getenv("SONG_MAPPING_PATH", root_dir / "dataset" / "song_mapping.csv")),
        help="Path to song_mapping.csv",
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        default=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        help="MongoDB connection URI",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=os.getenv("MONGO_DB_NAME", "music_recommendation"),
        help="MongoDB database name",
    )

    args = parser.parse_args()

    logger.info("Connecting to MongoDB at %s (database: %s)", args.mongo_uri, args.db_name)
    rec_count = import_recommendations_to_mongo(args.mahout_path, args.mongo_uri, args.db_name)
    song_count = import_song_mappings_to_mongo(args.song_mapping, args.mongo_uri, args.db_name)

    logger.info(f"Ingestion complete! Total users: {rec_count}, Total songs: {song_count}")


if __name__ == "__main__":
    main()
