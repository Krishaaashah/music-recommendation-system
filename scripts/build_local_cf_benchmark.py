#!/usr/bin/env python3
"""Build a deterministic train-only item-CF benchmark for the Last.fm data.

This is a lightweight local fallback for machines where the Mahout container is
not available. It keeps the same numeric user/item IDs as the Mahout output and
uses a deterministic leave-one-item-out split per user for evaluation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import math
from collections import Counter, defaultdict
from pathlib import Path


def load_mapping(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row[0].strip(): row[1].strip() for row in csv.reader(handle) if len(row) >= 2}


def read_histories(dataset: Path, song_map: dict[str, str], user_map: dict[str, str], keep: int) -> dict[str, list[tuple[str, int]]]:
    histories: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for raw in dataset.open("r", encoding="utf-8", errors="replace"):
        fields = raw.rstrip("\n").split("\t")
        if len(fields) < 3:
            continue
        user_hash, song_code = fields[0].strip(), fields[1].strip()
        item_id = song_map.get(song_code)
        if not item_id:
            continue
        try:
            plays = max(1, int(fields[2]))
        except ValueError:
            plays = 1
        row = histories[user_map.get(user_hash, user_hash)]
        row.append((item_id, plays))

    for user_id, rows in histories.items():
        # The prepared Last.fm file is already aggregated, but merging here
        # keeps this tool correct for raw triplet files too.
        merged: dict[str, int] = defaultdict(int)
        for item_id, plays in rows:
            merged[item_id] += plays
        histories[user_id] = heapq.nlargest(keep, merged.items(), key=lambda pair: (pair[1], pair[0]))
    return histories


def choose_holdout(user_id: str, items: list[tuple[str, int]]) -> str:
    if len(items) <= 1:
        return ""
    digest = hashlib.sha1(user_id.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % min(len(items), 100)
    return items[index][0]


def build_neighbors(histories: dict[str, list[tuple[str, int]]], heldout: dict[str, str], pair_items: int) -> dict[str, Counter[str]]:
    neighbors: dict[str, Counter[str]] = defaultdict(Counter)
    for user_id, rows in histories.items():
        test_item = heldout.get(user_id, "")
        items = [item_id for item_id, _ in rows if item_id != test_item][:pair_items]
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                neighbors[left][right] += 1
                neighbors[right][left] += 1
    return neighbors


def build_user_index(histories: dict[str, list[tuple[str, int]]], heldout: dict[str, str]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for user_id, rows in histories.items():
        test_item = heldout.get(user_id, "")
        for item_id, _ in rows[:100]:
            if item_id != test_item:
                index[item_id].append(user_id)
    return index


def load_artist_candidates(metadata: Path, history_items: set[str]) -> dict[str, str]:
    item_artist: dict[str, str] = {}
    with metadata.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            item_id = (row.get("item_id") or "").strip()
            artist = (row.get("artist_name") or "").strip().casefold()
            if item_id in history_items and artist:
                item_artist[item_id] = artist
    return item_artist


def recommend(
    items: list[tuple[str, int]],
    neighbors: dict[str, Counter[str]],
    popularity: Counter[str],
    item_artist: dict[str, str],
    artist_items: dict[str, list[tuple[str, int]]],
    user_index: dict[str, list[str]],
    histories: dict[str, list[tuple[str, int]]],
    limit: int,
) -> list[tuple[str, float]]:
    seen = {item_id for item_id, _ in items}
    scores: Counter[str] = Counter()
    for item_id, plays in items[:40]:
        weight = 1.0 + math.log1p(plays)
        for candidate, count in neighbors.get(item_id, {}).most_common(80):
            if candidate not in seen:
                scores[candidate] += weight * count
    similar_users: Counter[str] = Counter()
    for item_id, _ in items[:100]:
        for other_user in user_index.get(item_id, []):
            similar_users[other_user] += 1
    for other_user, shared in similar_users.most_common(40):
        other_rows = histories.get(other_user, [])
        similarity = shared / max(1.0, math.sqrt(len(items) * len(other_rows)))
        for candidate, plays in other_rows[:100]:
            if candidate not in seen:
                scores[candidate] += 20.0 * similarity * (1.0 + math.log1p(plays))
    artist_strength: Counter[str] = Counter()
    for item_id, plays in items:
        if artist := item_artist.get(item_id):
            artist_strength[artist] += 1.0 + math.log1p(plays)
    for artist, strength in artist_strength.items():
        for candidate, plays in artist_items.get(artist, [])[:100]:
            if candidate not in seen:
                scores[candidate] += 3.0 * strength + 0.02 * math.log1p(plays)
    # Popularity is a low-weight tie breaker, not a replacement for CF.
    for candidate, plays in popularity.most_common(500):
        if candidate not in seen:
            scores[candidate] += 0.01 * math.log1p(plays)
    return heapq.nlargest(limit, scores.items(), key=lambda pair: (pair[1], pair[0]))


def score(recommendations: dict[str, list[str]], holdout: dict[str, str], k: int) -> dict[str, float]:
    values = {"precision": [], "recall": [], "mrr": [], "hit": []}
    for user_id, actual in holdout.items():
        if not actual or not recommendations.get(user_id):
            continue
        predicted = recommendations[user_id][:k]
        try:
            rank = predicted.index(actual) + 1
        except ValueError:
            rank = 0
        hit = int(rank > 0)
        values["precision"].append(hit / k)
        values["recall"].append(hit)
        values["mrr"].append(1.0 / rank if rank else 0.0)
        values["hit"].append(hit)
    count = len(values["hit"])
    if not count:
        return {key: 0.0 for key in values} | {"users": 0}
    return {key: round(sum(series) / count, 6) for key, series in values.items()} | {"users": count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("dataset/lastfm/train_triplets.txt"))
    parser.add_argument("--song-map", type=Path, default=Path("dataset/lastfm/song_mapping.csv"))
    parser.add_argument("--user-map", type=Path, default=Path("dataset/lastfm/user_mapping.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("dataset/lastfm/song_metadata.csv"))
    parser.add_argument("--output", type=Path, default=Path("output/local-cf-train-split/part-r-00000"))
    parser.add_argument("--history-size", type=int, default=100)
    parser.add_argument("--pair-items", type=int, default=40)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    song_map = load_mapping(args.song_map)
    user_map = load_mapping(args.user_map)
    histories = read_histories(args.dataset, song_map, user_map, args.history_size)
    history_items = {item_id for rows in histories.values() for item_id, _ in rows}
    item_artist = load_artist_candidates(args.metadata, history_items)
    popularity: Counter[str] = Counter()
    for rows in histories.values():
        popularity.update({item_id: plays for item_id, plays in rows})
    heldout = {user_id: choose_holdout(user_id, rows) for user_id, rows in histories.items()}
    neighbors = build_neighbors(histories, heldout, args.pair_items)
    user_index = build_user_index(histories, heldout)
    artist_items: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for user_id, rows in histories.items():
        for item_id, plays in rows:
            if item_id != heldout.get(user_id, "") and (artist := item_artist.get(item_id)):
                artist_items[artist].append((item_id, plays))
    for artist in artist_items:
        merged: Counter[str] = Counter(dict(artist_items[artist]))
        artist_items[artist] = merged.most_common(100)

    train_recommendations: dict[str, list[str]] = {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for user_id, rows in sorted(histories.items(), key=lambda pair: int(pair[0]) if pair[0].isdigit() else pair[0]):
            train_rows = [(item_id, plays) for item_id, plays in rows if item_id != heldout.get(user_id, "")]
            ranked = recommend(train_rows, neighbors, popularity, item_artist, artist_items, user_index, histories, args.k)
            train_recommendations[user_id] = [item_id for item_id, _ in ranked]
            payload = ",".join(f"{item_id}:{score:.6f}" for item_id, score in ranked)
            if payload:
                handle.write(f"{user_id}\t[{payload}]\n")

    metrics = score(train_recommendations, heldout, args.k)
    print(f"Generated {len(train_recommendations):,} train-only user profiles at {args.output}")
    print(f"Precision@{args.k}: {metrics['precision']:.6f}")
    print(f"Recall@{args.k}: {metrics['recall']:.6f}")
    print(f"MRR@{args.k}: {metrics['mrr']:.6f}")
    print(f"Hit Rate@{args.k}: {metrics['hit']:.6f}")
    print(f"Evaluated users: {metrics['users']:,}")


if __name__ == "__main__":
    main()
