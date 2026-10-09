#!/usr/bin/env python3
"""
Recommendation Evaluation Pipeline
Evaluates Apache Mahout Item-Based Collaborative Filtering recommendations
against an offline holdout test set from the Echo Nest 1M interaction dataset.

Metrics computed:
- Precision@K
- Recall@K
- Mean Reciprocal Rank (MRR@K)
- Hit Rate@K
- Catalog Coverage
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_recommendations(rec_path: Path) -> dict[str, list[str]]:
    """Loads Mahout output part-r-00000 into a dict: user_id -> list of item_ids."""
    recs: dict[str, list[str]] = {}
    if not rec_path.exists():
        logger.error("Recommendation file not found: %s", rec_path)
        return recs

    lines = rec_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            parts = line.split("\t", 1)
            user_id = parts[0].strip()
            payload = parts[1].strip().strip("[]")
            items = []
            for pair in payload.split(","):
                if ":" in pair:
                    item_id = pair.split(":")[0].strip()
                    if item_id:
                        items.append(item_id)
            if user_id and items:
                recs[user_id] = items
    logger.info("Loaded recommendations for %d users from %s", len(recs), rec_path)
    return recs


def load_song_mapping(mapping_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Loads song_code <-> item_id bidirectional mappings."""
    code_to_item: dict[str, str] = {}
    item_to_code: dict[str, str] = {}
    if not mapping_path.exists():
        logger.warning("Song mapping not found: %s", mapping_path)
        return code_to_item, item_to_code

    with open(mapping_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                code, item_id = row[0].strip(), row[1].strip()
                code_to_item[code] = item_id
                item_to_code[item_id] = code
    logger.info("Loaded %d song mappings", len(code_to_item))
    return code_to_item, item_to_code


def load_user_mapping(mapping_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Loads user_hash <-> int_user_id bidirectional mappings."""
    hash_to_id: dict[str, str] = {}
    id_to_hash: dict[str, str] = {}
    if not mapping_path.exists():
        logger.warning("User mapping not found: %s", mapping_path)
        return hash_to_id, id_to_hash

    with open(mapping_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                uhash, uid = row[0].strip(), row[1].strip()
                hash_to_id[uhash] = uid
                id_to_hash[uid] = uhash
    logger.info("Loaded %d user mappings", len(hash_to_id))
    return hash_to_id, id_to_hash


def evaluate(
    recs: dict[str, list[str]],
    test_interactions: dict[str, set[str]],
    k: int = 10,
    total_catalog_size: int = 148040,
) -> dict[str, float]:
    """Computes Top-K ranking evaluation metrics."""
    hits = 0
    total_precision = 0.0
    total_recall = 0.0
    total_mrr = 0.0
    evaluated_users = 0
    recommended_items_set: set[str] = set()

    for user_id, actual_items in test_interactions.items():
        if user_id not in recs or not actual_items:
            continue

        predicted = recs[user_id][:k]
        recommended_items_set.update(predicted)

        # Hits
        hit_items = set(predicted) & actual_items
        num_hits = len(hit_items)
        if num_hits > 0:
            hits += 1

        # Precision@K
        precision = num_hits / float(k)
        total_precision += precision

        # Recall@K
        recall = num_hits / float(len(actual_items))
        total_recall += recall

        # MRR@K (Reciprocal rank of first hit)
        mrr = 0.0
        for rank, item in enumerate(predicted, 1):
            if item in actual_items:
                mrr = 1.0 / rank
                break
        total_mrr += mrr

        evaluated_users += 1

    if evaluated_users == 0:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "hit_rate_at_k": 0.0,
            "catalog_coverage_pct": 0.0,
            "evaluated_users": 0,
        }

    return {
        "k": k,
        "precision_at_k": round(total_precision / evaluated_users, 4),
        "recall_at_k": round(total_recall / evaluated_users, 4),
        "mrr_at_k": round(total_mrr / evaluated_users, 4),
        "hit_rate_at_k": round(hits / evaluated_users, 4),
        "catalog_coverage_pct": round((len(recommended_items_set) / float(total_catalog_size)) * 100, 2),
        "evaluated_users": evaluated_users,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Recommendation Model")
    parser.add_argument("--recommendations", type=str, default="output/mahout/part-r-00000")
    parser.add_argument("--song-mapping", type=str, default="dataset/song_mapping.csv")
    parser.add_argument("--user-mapping", type=str, default="dataset/user_mapping.csv")
    parser.add_argument("--dataset", type=str, default="dataset/train_triplets_1m.txt")
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()

    rec_path = Path(args.recommendations)
    recs = load_recommendations(rec_path)
    if not recs:
        logger.error("No recommendations loaded. Exiting.")
        sys.exit(1)

    code_to_item, item_to_code = load_song_mapping(Path(args.song_mapping))
    hash_to_id, id_to_hash = load_user_mapping(Path(args.user_mapping))

    logger.info("Sampling holdout interactions from %s...", args.dataset)
    dataset_path = Path(args.dataset)
    test_interactions: dict[str, set[str]] = defaultdict(set)

    # Read dataset and sample holdout for users with recommendations
    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i % 5 == 0:  # 20% holdout split
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        uhash, scode = parts[0].strip(), parts[1].strip()
                        uid = hash_to_id.get(uhash)
                        iid = code_to_item.get(scode)
                        if uid and iid and uid in recs:
                            test_interactions[uid].add(iid)
                if i >= 200000:  # Sample size for fast evaluation
                    break

    logger.info("Evaluating on %d test users with holdout interactions...", len(test_interactions))
    results = evaluate(recs, test_interactions, k=args.k, total_catalog_size=len(code_to_item) or 148040)

    print("\n========================================================")
    print("      RECOMMENDATION MODEL OFFLINE EVALUATION RESULTS   ")
    print("========================================================")
    print(f" Model: Apache Mahout Item-Based CF (SIMILARITY_LOGLIKELIHOOD)")
    print(f" Cutoff (K):             {results.get('k', args.k)}")
    print(f" Precision@{args.k}:           {results['precision_at_k']:.4f}")
    print(f" Recall@{args.k}:              {results['recall_at_k']:.4f}")
    print(f" MRR@{args.k} (Mean Reciprocal): {results['mrr_at_k']:.4f}")
    print(f" Hit Rate@{args.k}:            {results['hit_rate_at_k']:.4f} ({results['hit_rate_at_k']*100:.1f}%)")
    print(f" Catalog Coverage:       {results['catalog_coverage_pct']:.2f}%")
    print(f" Evaluated Users:        {results['evaluated_users']}")
    print("========================================================\n")


if __name__ == "__main__":
    main()
