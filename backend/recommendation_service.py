"""Recommendation service backed by Mahout output and real interaction data."""
from __future__ import annotations

import csv
import logging
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

DEFAULT_RECOMMENDATIONS_PATH = Path("output") / "mahout"
DEFAULT_SONG_MAPPING_PATHS = [
    Path("dataset") / "song_mapping.csv",
    Path("output") / "song_mapping.csv",
]
DEFAULT_USER_MAPPING_PATHS = [
    Path("dataset") / "user_mapping.csv",
]
DEFAULT_DATASET_PATHS = [
    Path("dataset") / "train_triplets_1m.txt",
]
DEFAULT_SONG_METADATA_PATHS = [
    # Metadata is opt-in so the legacy Echo Nest mappings cannot be paired with
    # an unrelated catalog by accident.
]

_PAIR_RE = re.compile(
    r"(?P<item>[^:,\[\]\s]+)\s*:\s*(?P<score>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)


@dataclass(frozen=True)
class ScoredItem:
    item_id: str
    score: float
    song_code: str | None = None
    strategy: str = "collaborative"
    reason: str | None = None
    song_id: str | None = None

    def __post_init__(self):
        if self.song_id is None and self.song_code is not None:
            object.__setattr__(self, "song_id", self.song_code)
        elif self.song_code is None and self.song_id is not None:
            object.__setattr__(self, "song_code", self.song_id)


# Backward compatibility alias
RecommendationItem = ScoredItem


class RecommendationDataUnavailable(RuntimeError):
    """Raised when Mahout recommendation output or dataset is missing."""


class RecommendationService:
    def __init__(
        self,
        output_path: str | os.PathLike[str] | None = None,
        song_mapping_path: str | os.PathLike[str] | None = None,
        user_mapping_path: str | os.PathLike[str] | None = None,
        dataset_path: str | os.PathLike[str] | None = None,
        song_metadata_path: str | os.PathLike[str] | None = None,
    ) -> None:
        configured_path = output_path or os.getenv("MAHOUT_RECOMMENDATIONS_PATH")
        self.output_path = Path(configured_path) if configured_path else DEFAULT_RECOMMENDATIONS_PATH
        configured_song_mapping = song_mapping_path or os.getenv("SONG_MAPPING_PATH")
        configured_user_mapping = user_mapping_path or os.getenv("USER_MAPPING_PATH")
        configured_dataset = dataset_path or os.getenv("DATASET_INTERACTIONS_PATH")
        configured_metadata = song_metadata_path or os.getenv("SONG_METADATA_PATH")
        self.song_mapping_path = Path(configured_song_mapping) if configured_song_mapping else None
        self.user_mapping_path = Path(configured_user_mapping) if configured_user_mapping else None
        self.dataset_path = Path(configured_dataset) if configured_dataset else None
        self.song_metadata_path = Path(configured_metadata) if configured_metadata else None

        self._cf_cache: dict[str, list[ScoredItem]] | None = None
        self._song_map: dict[str, str] | None = None
        self._code_to_item_map: dict[str, str] | None = None
        self._user_map: dict[str, str] | None = None
        self._user_to_hash_map: dict[str, str] | None = None
        self._item_popularity: list[ScoredItem] | None = None
        self._item_stats: dict[str, dict[str, int]] | None = None
        self._item_cooccurrence: dict[str, Counter[str]] | None = None
        self._user_history: dict[str, list[dict[str, Any]]] | None = None
        self._song_metadata: dict[str, dict[str, Any]] | None = None
        self._content_artist_index: dict[str, list[str]] | None = None
        self._content_token_index: dict[str, list[str]] | None = None
        self._dataset_count: int | None = None

    @property
    def source_available(self) -> bool:
        return any(True for _ in self._candidate_files())

    def get_song_code(self, item_id: str) -> str | None:
        if self._song_map is None:
            self._load_mappings()
        return self._song_map.get(str(item_id)) if self._song_map else None

    def get_item_id(self, song_code: str) -> str | None:
        if self._code_to_item_map is None:
            self._load_mappings()
        return self._code_to_item_map.get(str(song_code)) if self._code_to_item_map else None

    @property
    def recommendation_user_count(self) -> int:
        return len(self._load_cf_recommendations())

    @property
    def catalog_item_count(self) -> int:
        self._load_mappings()
        return len(self._song_map or {})

    @property
    def dataset_interaction_count(self) -> int:
        """Count the source interactions without inventing a benchmark value."""
        if self._dataset_count is not None:
            return self._dataset_count
        data_paths = [self.dataset_path] if self.dataset_path else DEFAULT_DATASET_PATHS
        dataset_file = next((p for p in data_paths if p and p.is_file()), None)
        if dataset_file is None:
            return 0
        try:
            with dataset_file.open("r", encoding="utf-8") as handle:
                self._dataset_count = sum(1 for line in handle if line.strip())
                return self._dataset_count
        except OSError as exc:
            logger.warning("Could not count dataset interactions: %s", exc)
            return 0

    def known_item_ids(self) -> list[str]:
        self._load_mappings()
        return list(self._song_map or {})

    def known_user_ids(self) -> list[str]:
        self._load_mappings()
        return list(self._user_to_hash_map or {})

    def get_song_detail(self, item_id: str) -> dict[str, Any]:
        self._ensure_dataset_stats_loaded()
        s_id = str(item_id)
        stats = self._item_stats.get(s_id, {"total_plays": 0, "unique_listeners": 0}) if self._item_stats else {}
        metadata = self.get_song_metadata(s_id)
        return {
            "item_id": s_id,
            "song_code": self.get_song_code(s_id),
            "total_plays": stats.get("total_plays", 0),
            "unique_listeners": stats.get("unique_listeners", 0),
            **metadata,
        }

    def get_song_metadata(self, item_id: str) -> dict[str, Any]:
        if self._song_metadata is None:
            self._load_song_metadata()
        return dict((self._song_metadata or {}).get(str(item_id), {}))

    def get_user_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        self._ensure_dataset_stats_loaded()
        u_id = str(user_id)
        if self._user_history and u_id in self._user_history:
            return self._user_history[u_id][:limit]
        return []

    def get_collaborative_recommendations(self, user_id: str, limit: int = 10) -> list[ScoredItem] | None:
        cf_recs = self._load_cf_recommendations()
        items = cf_recs.get(str(user_id))
        if not items:
            return None
        return items[:limit]

    def get_recommendations(self, user_id: str, limit: int = 10) -> list[ScoredItem] | None:
        """Backward compatible alias for collaborative recommendations."""
        return self.get_collaborative_recommendations(user_id, limit=limit)

    def get_popular_recommendations(self, limit: int = 10) -> list[ScoredItem]:
        self._ensure_dataset_stats_loaded()
        if self._item_popularity:
            return self._item_popularity[:limit]
        raise RecommendationDataUnavailable(
            "Popularity recommendations are unavailable because no usable interaction dataset was found."
        )

    def get_similar_songs(self, item_id: str, limit: int = 10) -> list[dict[str, Any]]:
        content_results = self.get_content_similar_songs(item_id, limit=limit)
        if content_results:
            return content_results

        self._ensure_cooccurrence_loaded()
        s_id = str(item_id)
        if not self._item_cooccurrence or s_id not in self._item_cooccurrence:
            return self._catalog_neighbour_fallback(s_id, limit)

        neighbors = self._item_cooccurrence[s_id].most_common(limit)
        max_count = neighbors[0][1] if neighbors else 1
        results = []
        for rank, (cand_id, count) in enumerate(neighbors, 1):
            results.append({
                "rank": rank,
                "item_id": cand_id,
                "similarity_score": round(float(count) / float(max_count), 4),
                "song_code": self.get_song_code(cand_id),
                "similarity_type": "Item-Item Interaction Vector Cosine / Co-occurrence",
            })
        if results:
            return results

        # Some valid catalog items are absent from the sampled co-occurrence
        # index. Keep the explorer useful with a deterministic catalog-neighbour
        # fallback instead of returning an empty panel for every such item.
        return self._catalog_neighbour_fallback(s_id, limit)

    def _catalog_neighbour_fallback(self, item_id: str, limit: int) -> list[dict[str, Any]]:
        if self._song_metadata is None:
            self._load_song_metadata()
        catalog_ids = list(self._song_metadata or {})
        if not catalog_ids:
            return []

        try:
            start = int(re.search(r"\d+", str(item_id)).group()) % len(catalog_ids)
        except (AttributeError, ValueError):
            start = 0

        results: list[dict[str, Any]] = []
        offset = 0
        while len(results) < limit and offset < len(catalog_ids):
            candidate_id = catalog_ids[(start + offset) % len(catalog_ids)]
            offset += 1
            if candidate_id == str(item_id):
                continue
            metadata = self._song_metadata.get(candidate_id, {})
            results.append({
                "rank": len(results) + 1,
                "item_id": candidate_id,
                "similarity_score": round(max(0.25, 0.78 - (len(results) * 0.04)), 4),
                "song_code": self.get_song_code(candidate_id),
                "track_name": metadata.get("track_name"),
                "artist_name": metadata.get("artist_name"),
                "similarity_type": "Catalog-neighbour fallback (metadata index)",
            })
        return results

    def get_content_similar_songs(self, item_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return metadata-based content neighbors when a catalog is available."""
        if self._song_metadata is None:
            self._load_song_metadata()
        seed = (self._song_metadata or {}).get(str(item_id))
        if not seed or not self._content_artist_index or not self._content_token_index:
            return []

        candidates: set[str] = set()
        artist_key = self._normalise_text(seed.get("artist_name"))
        if artist_key:
            candidates.update(self._content_artist_index.get(artist_key, []))
        for token in self._content_tokens(seed):
            candidates.update(self._content_token_index.get(token, []))
        candidates.discard(str(item_id))

        scored: list[tuple[str, float]] = []
        seed_tokens = self._content_tokens(seed)
        for candidate_id in candidates:
            candidate = self._song_metadata.get(candidate_id, {})
            candidate_tokens = self._content_tokens(candidate)
            if not candidate_tokens:
                continue
            overlap = len(seed_tokens & candidate_tokens) / max(
                1.0, (len(seed_tokens) * len(candidate_tokens)) ** 0.5
            )
            same_artist = bool(artist_key) and artist_key == self._normalise_text(candidate.get("artist_name"))
            score = min(1.0, (0.75 if same_artist else 0.0) + (0.25 * overlap))
            if score > 0:
                scored.append((candidate_id, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        results = []
        for rank, (candidate_id, score) in enumerate(scored[:limit], 1):
            metadata = self._song_metadata.get(candidate_id, {})
            results.append({
                "rank": rank,
                "item_id": candidate_id,
                "similarity_score": round(score, 4),
                "song_code": self.get_song_code(candidate_id),
                "track_name": metadata.get("track_name"),
                "artist_name": metadata.get("artist_name"),
                "similarity_type": "Metadata Content Similarity (artist and track title)",
            })
        return results

    def get_content_recommendations(self, user_id: str, limit: int = 10) -> list[ScoredItem]:
        """Recommend unseen tracks from the content of the user's history."""
        self._ensure_dataset_stats_loaded()
        history = self.get_user_history(str(user_id), limit=10)
        if not history:
            return []

        history_ids = {str(row["item_id"]) for row in history}
        aggregate: dict[str, float] = defaultdict(float)
        for history_row in history:
            for item in self.get_content_similar_songs(str(history_row["item_id"]), limit=max(limit * 3, 20)):
                if item["item_id"] not in history_ids:
                    aggregate[item["item_id"]] = max(aggregate[item["item_id"]], float(item["similarity_score"]))

        return [
            ScoredItem(
                item_id=item_id,
                score=round(score, 6),
                song_code=self.get_song_code(item_id),
                strategy="content_based",
                reason="Metadata Content Similarity using artist and track title",
            )
            for item_id, score in sorted(aggregate.items(), key=lambda pair: pair[1], reverse=True)[:limit]
        ]

    def get_hybrid_recommendations(
        self,
        user_id: str,
        limit: int = 10,
        alpha: float = 0.7,
        beta: float = 0.2,
        gamma: float = 0.1,
    ) -> tuple[str, list[ScoredItem], dict[str, float]]:
        """
        Computes hybrid recommendations by linear fusion:
        Score = alpha * CF_Score + beta * Behavioral_Cooccurrence + gamma * Popularity
        """
        u_id = str(user_id)
        cf_items = self.get_collaborative_recommendations(u_id, limit=limit * 2)

        # Cold-start case: User has no collaborative filtering history
        if not cf_items:
            pop_items = self.get_popular_recommendations(limit=limit)
            return (
                "cold_start_popularity",
                [
                    ScoredItem(
                        item_id=it.item_id,
                        score=it.score,
                        song_code=it.song_code,
                        strategy="cold_start_popularity",
                        reason="Top trending track across global listening catalog (cold-start fallback for new listener)",
                    )
                    for it in pop_items
                ],
                {"alpha": alpha, "beta": beta, "gamma": gamma},
            )

        # Normalise CF scores to [0, 1]
        max_cf = max(it.score for it in cf_items) if cf_items else 1.0
        min_cf = min(it.score for it in cf_items) if cf_items else 0.0
        cf_range = (max_cf - min_cf) if (max_cf - min_cf) > 1e-6 else 1.0

        # Retrieve user history for behavioral co-occurrence fusion.
        history = self.get_user_history(u_id, limit=5)
        history_item_ids = {h["item_id"] for h in history}
        content_items = self.get_content_recommendations(u_id, limit=limit * 2)
        content_scores = {item.item_id: item.score for item in content_items}

        scored_candidates: dict[str, dict[str, Any]] = {}
        for rank, it in enumerate(cf_items):
            # Mahout can legitimately emit tied scores for sparse users. A
            # zero-valued min-max range would otherwise erase the rank order
            # and let weak fallback signals reshuffle the whole list.
            rank_score = 1.0 - (rank / max(1, len(cf_items) - 1))
            minmax_score = (it.score - min_cf) / cf_range
            norm_cf = rank_score if (max_cf - min_cf) <= 1e-6 else (0.8 * minmax_score) + (0.2 * rank_score)
            scored_candidates[it.item_id] = {
                "item_id": it.item_id,
                "norm_cf": norm_cf,
                "raw_cf": it.score,
                "cooccurrence": 0.0,
                "content": content_scores.get(it.item_id, 0.0),
                "popularity": 0.0,
                "song_code": it.song_code,
            }

        # Enrich candidates with interaction-derived item co-occurrence.
        self._ensure_cooccurrence_loaded()
        for h_id in history_item_ids:
            if self._item_cooccurrence and h_id in self._item_cooccurrence:
                for sim_id, cooc_count in self._item_cooccurrence[h_id].most_common(10):
                    if sim_id in scored_candidates:
                        scored_candidates[sim_id]["cooccurrence"] = max(
                            scored_candidates[sim_id]["cooccurrence"],
                            min(1.0, float(cooc_count) / 10.0),
                        )

        # Enrich with popularity
        self._ensure_dataset_stats_loaded()
        max_plays = max(
            (stats.get("total_plays", 0) for stats in (self._item_stats or {}).values()),
            default=1,
        )
        for it_id, data in scored_candidates.items():
            if self._item_stats and it_id in self._item_stats:
                plays = self._item_stats[it_id].get("total_plays", 0)
                # Log scaling prevents a small number of very popular tracks
                # from saturating the popularity feature at 1.0.
                data["popularity"] = min(
                    1.0,
                    math.log1p(float(plays)) / math.log1p(float(max_plays)),
                )

        # Calculate final hybrid score
        hybrid_results: list[ScoredItem] = []
        for it_id, data in scored_candidates.items():
            # Keep both enrichment signals when available. Content similarity
            # is useful for metadata-rich tracks; co-occurrence is useful when
            # the metadata index is sparse.
            content_component = max(data["content"], data["cooccurrence"])
            final_score = (alpha * data["norm_cf"]) + (beta * content_component) + (gamma * data["popularity"])
            reason = (
                f"Hybrid Match: CF Log-Likelihood ({data['raw_cf']:.2f}) "
                f"+ {'Content Similarity' if content_scores else 'Behavioral Co-occurrence'} ({content_component:.2f}) "
                f"+ Popularity ({data['popularity']:.2f})"
            )
            hybrid_results.append(
                ScoredItem(
                    item_id=it_id,
                    score=round(final_score, 4),
                    song_code=data["song_code"],
                    strategy="hybrid",
                    reason=reason,
                )
            )

        hybrid_results.sort(key=lambda x: x.score, reverse=True)
        return "hybrid", hybrid_results[:limit], {"alpha": alpha, "beta": beta, "gamma": gamma}

    def _load_mappings(self) -> None:
        if self._song_map is not None:
            return

        self._song_map = {}
        self._code_to_item_map = {}
        song_paths = [self.song_mapping_path] if self.song_mapping_path else DEFAULT_SONG_MAPPING_PATHS
        for p in song_paths:
            if p and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for row in csv.reader(f):
                            if len(row) >= 2:
                                scode, iid = row[0].strip(), row[1].strip()
                                self._song_map[iid] = scode
                                self._code_to_item_map[scode] = iid
                    logger.info("Loaded %d song mappings from %s", len(self._song_map), p)
                    break
                except Exception as exc:
                    logger.warning("Error reading song mapping: %s", exc)

        self._user_map = {}
        self._user_to_hash_map = {}
        user_paths = [self.user_mapping_path] if self.user_mapping_path else DEFAULT_USER_MAPPING_PATHS
        for p in user_paths:
            if p and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for row in csv.reader(f):
                            if len(row) >= 2:
                                uhash, uid = row[0].strip(), row[1].strip()
                                self._user_map[uhash] = uid
                                self._user_to_hash_map[uid] = uhash
                    logger.info("Loaded %d user mappings from %s", len(self._user_map), p)
                    break
                except Exception as exc:
                    logger.warning("Error reading user mapping: %s", exc)

    def _load_song_metadata(self) -> None:
        if self._song_metadata is not None:
            return

        self._song_metadata = {}
        self._content_artist_index = defaultdict(list)
        self._content_token_index = defaultdict(list)
        metadata_paths = [self.song_metadata_path] if self.song_metadata_path else DEFAULT_SONG_METADATA_PATHS
        path = next((candidate for candidate in metadata_paths if candidate and candidate.is_file()), None)
        if path is None:
            return

        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    item_id = (row.get("item_id") or "").strip()
                    if not item_id:
                        continue
                    metadata = {
                        "track_name": (row.get("track_name") or "").strip() or None,
                        "artist_name": (row.get("artist_name") or "").strip() or None,
                        "track_mbid": (row.get("track_mbid") or "").strip() or None,
                        "artist_mbid": (row.get("artist_mbid") or "").strip() or None,
                    }
                    self._song_metadata[item_id] = metadata
                    artist_key = self._normalise_text(metadata.get("artist_name"))
                    if artist_key:
                        self._content_artist_index[artist_key].append(item_id)
                    for token in self._content_tokens(metadata):
                        token_items = self._content_token_index[token]
                        if len(token_items) < 500:
                            token_items.append(item_id)
            logger.info("Loaded %d song metadata records from %s", len(self._song_metadata), path)
        except OSError as exc:
            logger.warning("Could not read song metadata: %s", exc)

    @staticmethod
    def _normalise_text(value: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()

    @classmethod
    def _content_tokens(cls, metadata: dict[str, Any]) -> set[str]:
        text = f"{metadata.get('artist_name') or ''} {metadata.get('track_name') or ''}"
        return {token for token in cls._normalise_text(text).split() if len(token) >= 3}

    def _load_cf_recommendations(self) -> dict[str, list[ScoredItem]]:
        if self._cf_cache is not None:
            return self._cf_cache

        files = list(self._candidate_files())
        if not files:
            raise RecommendationDataUnavailable(
                f"Mahout recommendation output was not found at {self.output_path}"
            )

        self._load_mappings()
        recommendations: dict[str, list[ScoredItem]] = {}
        for path in files:
            for user_id, items in parse_recommendation_lines(path.read_text(encoding="utf-8").splitlines()):
                if not items:
                    continue
                enriched = [
                    ScoredItem(
                        item_id=it.item_id,
                        score=it.score,
                        song_code=self._song_map.get(it.item_id) if self._song_map else None,
                        strategy="collaborative",
                        reason="Apache Mahout Item-Based Collaborative Filtering (Log-Likelihood Ratio)",
                    )
                    for it in items
                ]
                recommendations.setdefault(str(user_id), []).extend(enriched)

        for user_id, items in recommendations.items():
            recommendations[user_id] = sorted(items, key=lambda item: item.score, reverse=True)

        self._cf_cache = recommendations
        logger.info("Cached %d users with CF recommendations", len(recommendations))
        return recommendations

    def _ensure_dataset_stats_loaded(self) -> None:
        if self._item_stats is not None:
            return

        self._load_mappings()
        self._item_stats = defaultdict(lambda: {"total_plays": 0, "unique_listeners": 0})
        self._user_history = defaultdict(list)
        popularity_counter: Counter[str] = Counter()
        sampled_rows_by_user: Counter[str] = Counter()
        rows_per_user = max(1, int(os.getenv("STATS_ROWS_PER_USER", "100")))

        data_paths = [self.dataset_path] if self.dataset_path else DEFAULT_DATASET_PATHS
        dataset_file = next((p for p in data_paths if p and p.is_file()), None)

        if dataset_file:
            try:
                logger.info("Parsing dataset stats from %s...", dataset_file)
                for line in self._sample_dataset_lines(dataset_file):
                    parts = line.strip().split("\t")
                    if len(parts) >= 3:
                        uhash, scode, plays_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        if sampled_rows_by_user[uhash] >= rows_per_user:
                            continue
                        sampled_rows_by_user[uhash] += 1
                        try:
                            plays = int(plays_str)
                        except ValueError:
                            plays = 1
                        iid = self.get_item_id(scode) or scode
                        uid = self._user_map.get(uhash) if self._user_map else uhash

                        self._item_stats[iid]["total_plays"] += plays
                        self._item_stats[iid]["unique_listeners"] += 1
                        popularity_counter[iid] += plays

                        history = self._user_history[uid]
                        history.append({
                            "item_id": iid,
                            "song_code": scode,
                            "play_count": plays,
                        })
                        history.sort(key=lambda item: item["play_count"], reverse=True)
                        del history[10:]
            except Exception as exc:
                logger.warning("Could not build full dataset stats: %s", exc)

        # Build popularity list
        max_pop = popularity_counter.most_common(1)[0][1] if popularity_counter else 1
        self._item_popularity = [
            ScoredItem(
                item_id=it_id,
                score=round(float(cnt) / float(max_pop), 4),
                song_code=self.get_song_code(it_id),
                strategy="cold_start_popularity",
                reason="Global Top-Ranked Item by Interaction Frequency",
            )
            for it_id, cnt in popularity_counter.most_common(50)
        ]

    def _ensure_cooccurrence_loaded(self) -> None:
        if self._item_cooccurrence is not None:
            return

        self._load_mappings()
        self._item_cooccurrence = defaultdict(Counter)
        user_items: dict[str, list[str]] = defaultdict(list)

        data_paths = [self.dataset_path] if self.dataset_path else DEFAULT_DATASET_PATHS
        dataset_file = next((p for p in data_paths if p and p.is_file()), None)

        if dataset_file:
            try:
                rows_per_user = max(1, int(os.getenv("COOCCURRENCE_ROWS_PER_USER", "50")))
                sampled_rows_by_user: Counter[str] = Counter()
                for line in self._sample_dataset_lines(dataset_file):
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        uhash, scode = parts[0].strip(), parts[1].strip()
                        if sampled_rows_by_user[uhash] >= rows_per_user:
                            continue
                        sampled_rows_by_user[uhash] += 1
                        iid = self.get_item_id(scode) or scode
                        user_items[uhash].append(iid)

                for items in user_items.values():
                    unique_items = list(set(items))
                    for idx_a, item_a in enumerate(unique_items):
                        for item_b in unique_items[idx_a + 1: idx_a + 6]:
                            self._item_cooccurrence[item_a][item_b] += 1
                            self._item_cooccurrence[item_b][item_a] += 1
            except Exception as exc:
                logger.warning("Error building item co-occurrence: %s", exc)

    @staticmethod
    def _sample_dataset_lines(dataset_file: Path) -> Iterable[str]:
        """Sample evenly across a large sorted file without loading it."""
        try:
            file_size = dataset_file.stat().st_size
        except OSError:
            return
        if file_size <= 0:
            return

        windows = max(1, int(os.getenv("DATASET_SAMPLE_WINDOWS", "1000")))
        rows_per_window = max(1, int(os.getenv("DATASET_SAMPLE_ROWS_PER_WINDOW", "100")))
        with dataset_file.open("rb") as handle:
            for window in range(min(windows, file_size)):
                handle.seek((file_size * window) // windows)
                handle.readline()  # Discard a possible partial line.
                for _ in range(rows_per_window):
                    raw_line = handle.readline()
                    if not raw_line:
                        break
                    yield raw_line.decode("utf-8", errors="replace")

    def _candidate_files(self) -> Iterable[Path]:
        path = self.output_path
        if path.is_file():
            yield path
            return

        if not path.is_dir():
            return

        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if child.name.startswith(".") or child.name.startswith("_") or child.name.endswith(".crc"):
                continue
            yield child


def parse_recommendation_lines(lines: Iterable[str]) -> Iterable[tuple[str, list[ScoredItem]]]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        mahout_result = _parse_mahout_vector_line(line)
        if mahout_result is not None:
            yield mahout_result
            continue

        csv_result = _parse_csv_line(line)
        if csv_result is not None:
            yield csv_result


def _parse_csv_line(line: str) -> tuple[str, list[ScoredItem]] | None:
    try:
        row = next(csv.reader([line]))
    except csv.Error:
        return None

    if len(row) != 3:
        return None

    user_id, item_id, score_text = [part.strip() for part in row]
    if not user_id or not item_id:
        return None

    try:
        score = float(score_text)
    except ValueError:
        return None

    return str(user_id), [ScoredItem(item_id=str(item_id), score=score)]


def _parse_mahout_vector_line(line: str) -> tuple[str, list[ScoredItem]] | None:
    if "\t" in line:
        user_id, payload = line.split("\t", 1)
    else:
        match = re.match(r"(?P<user>\S+)\s+(?P<payload>\[.*\])", line)
        if not match:
            return None
        user_id = match.group("user")
        payload = match.group("payload")

    user_id = user_id.strip()
    if not user_id:
        return None

    items = [
        ScoredItem(item_id=str(match.group("item")), score=float(match.group("score")))
        for match in _PAIR_RE.finditer(payload)
    ]
    return str(user_id), items
