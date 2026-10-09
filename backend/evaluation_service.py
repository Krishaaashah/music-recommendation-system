"""Compute offline ranking metrics from the checked-in Mahout output and data."""
from __future__ import annotations

import csv
import logging
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.recommendation_service import RecommendationDataUnavailable, parse_recommendation_lines

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    k: int
    precision_at_k: float
    recall_at_k: float
    mrr_at_k: float
    hit_rate_at_k: float
    map_at_k: float
    ndcg_at_k: float
    catalog_coverage_pct: float
    evaluated_users_count: int
    total_catalog_items: int
    evaluation_strategy: str
    dataset_split: str
    description: str


class EvaluationService:
    def __init__(
        self,
        recommendations_path: str | Path = "output/mahout",
        dataset_path: str | Path = "dataset/train_triplets_1m.txt",
        song_mapping_path: str | Path = "dataset/song_mapping.csv",
        user_mapping_path: str | Path = "dataset/user_mapping.csv",
        k: int = 10,
    ) -> None:
        self.recommendations_path = Path(
            os.getenv("MAHOUT_RECOMMENDATIONS_PATH", recommendations_path)
        )
        self.dataset_path = Path(os.getenv("DATASET_INTERACTIONS_PATH", dataset_path))
        self.song_mapping_path = Path(os.getenv("SONG_MAPPING_PATH", song_mapping_path))
        self.user_mapping_path = Path(os.getenv("USER_MAPPING_PATH", user_mapping_path))
        self.k = k
        # Keep the legacy test dataset exact by default; the active Last.fm
        # compose profile sets a bounded scan explicitly for fast demos.
        self.max_rows = max(0, int(os.getenv("EVALUATION_MAX_ROWS", "0")))
        self._metrics: EvaluationMetrics | None = None
        self._user_ids: dict[str, str] | None = None

    def get_metrics(self) -> EvaluationMetrics:
        if self._metrics is None:
            self._metrics = self._compute_metrics()
        return self._metrics

    def _compute_metrics(self) -> EvaluationMetrics:
        try:
            recommendations = self._load_recommendations()
        except RecommendationDataUnavailable as exc:
            return self._empty_metrics(str(exc))

        recommended_item_ids = {
            item_id
            for items in recommendations.values()
            for item_id in items[: self.k]
        }
        # The unbounded mode preserves the original exact evaluation contract.
        # The bounded demo mode only needs IDs that can appear in Top-K output,
        # which avoids a second full catalog dictionary in the API process.
        code_to_item = self._load_song_mapping(recommended_item_ids if self.max_rows else None)
        if not self.dataset_path.is_file() or not code_to_item:
            return self._empty_metrics("The dataset or song mapping is unavailable.")

        holdout: dict[str, set[str]] = defaultdict(set)
        total_rows = 0
        with self.dataset_path.open("r", encoding="utf-8") as handle:
            for row_number, line in enumerate(handle):
                if self.max_rows and row_number >= self.max_rows:
                    break
                if not line.strip():
                    continue
                total_rows += 1
                if row_number % 5 != 0:
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                user_id = self._user_id_for_hash(parts[0].strip())
                item_id = code_to_item.get(parts[1].strip())
                if item_id and user_id in recommendations:
                    holdout[user_id].add(item_id)

        catalog_size = self._count_mapping_rows()
        metrics = self._score(recommendations, holdout, catalog_size)
        metrics.evaluation_strategy = "Deterministic 20% holdout from the available interaction file"
        sample_note = f"first {self.max_rows:,} rows" if self.max_rows else "all source rows"
        metrics.dataset_split = f"80% train / 20% test by row modulo 5; {total_rows:,} source rows scanned ({sample_note})"
        metrics.description = (
            "Measured against the checked-in Mahout recommendation output. "
            "A zero value means no valid user/item overlap was available for that metric."
        )
        return metrics

    def _load_recommendations(self) -> dict[str, list[str]]:
        if self.recommendations_path.is_file():
            files = [self.recommendations_path]
        elif self.recommendations_path.is_dir():
            files = sorted(
                p for p in self.recommendations_path.rglob("*")
                if p.is_file() and not p.name.startswith((".", "_")) and not p.name.endswith(".crc")
            )
        else:
            files = []
        if not files:
            raise RecommendationDataUnavailable(f"Recommendation output was not found at {self.recommendations_path}")

        parsed: dict[str, list[str]] = {}
        for path in files:
            for user_id, items in parse_recommendation_lines(path.read_text(encoding="utf-8").splitlines()):
                if items:
                    parsed.setdefault(user_id, []).extend(item.item_id for item in items)
        if not parsed:
            raise RecommendationDataUnavailable("Recommendation output contained no parseable records")
        return parsed

    def _load_song_mapping(self, only_item_ids: set[str] | None = None) -> dict[str, str]:
        if not self.song_mapping_path.is_file():
            return {}
        mapping: dict[str, str] = {}
        with self.song_mapping_path.open("r", encoding="utf-8") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2:
                    item_id = row[1].strip()
                    if only_item_ids is None or item_id in only_item_ids:
                        mapping[row[0].strip()] = item_id
        return mapping

    def _count_mapping_rows(self) -> int:
        if not self.song_mapping_path.is_file():
            return 0
        with self.song_mapping_path.open("r", encoding="utf-8") as handle:
            return sum(1 for row in csv.reader(handle) if len(row) >= 2)

    def _user_id_for_hash(self, user_hash: str) -> str:
        if self._user_ids is None:
            self._user_ids = {}
            if self.user_mapping_path.is_file():
                with self.user_mapping_path.open("r", encoding="utf-8") as handle:
                    for row in csv.reader(handle):
                        if len(row) >= 2:
                            self._user_ids[row[0].strip()] = row[1].strip()
        return self._user_ids.get(user_hash, user_hash)

    def _score(
        self,
        recommendations: dict[str, list[str]],
        holdout: dict[str, set[str]],
        catalog_size: int,
    ) -> EvaluationMetrics:
        precision = recall = mrr = hit_rate = mean_ap = mean_ndcg = 0.0
        recommended_items: set[str] = set()
        evaluated = 0
        for user_id, actual in holdout.items():
            predicted = recommendations.get(user_id, [])[: self.k]
            if not predicted or not actual:
                continue
            evaluated += 1
            recommended_items.update(predicted)
            hits = [rank for rank, item in enumerate(predicted, 1) if item in actual]
            precision += len(hits) / self.k
            recall += len(hits) / len(actual)
            hit_rate += bool(hits)
            mrr += 1.0 / hits[0] if hits else 0.0

            running_hits = 0
            average_precision = 0.0
            for rank, item in enumerate(predicted, 1):
                if item in actual:
                    running_hits += 1
                    average_precision += running_hits / rank
            mean_ap += average_precision / min(len(actual), self.k)

            dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
            ideal_dcg = sum(
                1.0 / math.log2(rank + 1) for rank in range(1, min(len(actual), self.k) + 1)
            ) or 1.0
            mean_ndcg += dcg / ideal_dcg

        if evaluated == 0:
            return self._empty_metrics("No users had both Mahout output and holdout interactions.")

        return EvaluationMetrics(
            k=self.k,
            precision_at_k=round(precision / evaluated, 6),
            recall_at_k=round(recall / evaluated, 6),
            mrr_at_k=round(mrr / evaluated, 6),
            hit_rate_at_k=round(hit_rate / evaluated, 6),
            map_at_k=round(mean_ap / evaluated, 6),
            ndcg_at_k=round(mean_ndcg / evaluated, 6),
            catalog_coverage_pct=round((len(recommended_items) / catalog_size) * 100, 6) if catalog_size else 0.0,
            evaluated_users_count=evaluated,
            total_catalog_items=catalog_size,
            evaluation_strategy="",
            dataset_split="",
            description="",
        )

    def _empty_metrics(self, reason: str) -> EvaluationMetrics:
        return EvaluationMetrics(
            k=self.k,
            precision_at_k=0.0,
            recall_at_k=0.0,
            mrr_at_k=0.0,
            hit_rate_at_k=0.0,
            map_at_k=0.0,
            ndcg_at_k=0.0,
            catalog_coverage_pct=0.0,
            evaluated_users_count=0,
            total_catalog_items=0,
            evaluation_strategy="Not evaluated",
            dataset_split="Not evaluated",
            description=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.get_metrics().__dict__.copy()
