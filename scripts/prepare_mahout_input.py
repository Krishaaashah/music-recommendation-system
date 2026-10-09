"""
Data preparation script for Apache Mahout.
Maps alphanumeric user and song IDs to sequential integers required by Mahout,
and outputs mahout_input.csv with user_id,song_id,play_count.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def prepare_mahout_data(
    input_file: Path,
    output_csv: Path,
    user_map_file: Path,
    song_map_file: Path,
) -> tuple[int, int, int]:
    print(f"Reading dataset from {input_file}...")

    user_to_id: dict[str, int] = {}
    song_to_id: dict[str, int] = {}
    row_count = 0

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    user_map_file.parent.mkdir(parents=True, exist_ok=True)
    song_map_file.parent.mkdir(parents=True, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as fin, open(output_csv, "w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout)
        for line in fin:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            user_str, song_str, count_str = parts[0].strip(), parts[1].strip(), parts[2].strip()

            if user_str not in user_to_id:
                user_to_id[user_str] = len(user_to_id) + 1
            if song_str not in song_to_id:
                song_to_id[song_str] = len(song_to_id) + 1

            u_id = user_to_id[user_str]
            s_id = song_to_id[song_str]
            writer.writerow([u_id, s_id, count_str])
            row_count += 1

            if row_count % 200000 == 0:
                print(f"Processed {row_count} lines...")

    # Save user mappings
    with open(user_map_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for user_str, u_id in user_to_id.items():
            writer.writerow([user_str, u_id])

    # Save song mappings
    with open(song_map_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for song_str, s_id in song_to_id.items():
            writer.writerow([song_str, s_id])

    print(f"Finished! Total interactions: {row_count}, Unique users: {len(user_to_id)}, Unique songs: {len(song_to_id)}")
    return row_count, len(user_to_id), len(song_to_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare dataset for Mahout collaborative filtering.")
    parser.add_argument("--input", type=Path, default=Path("dataset/train_triplets_1m.txt"))
    parser.add_argument("--output", type=Path, default=Path("dataset/mahout_input.csv"))
    parser.add_argument("--user-map", type=Path, default=Path("dataset/user_mapping.csv"))
    parser.add_argument("--song-map", type=Path, default=Path("dataset/song_mapping.csv"))
    args = parser.parse_args()

    prepare_mahout_data(args.input, args.output, args.user_map, args.song_map)
