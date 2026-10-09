from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    rank: int = Field(default=1, description="Ranking position (1 to N)")
    item_id: str = Field(..., description="Item integer identifier")
    score: float = Field(..., description="Recommendation score / similarity metric")
    song_code: str | None = Field(default=None, description="Source dataset track identifier")
    song_id: str | None = Field(default=None, description="Source dataset track identifier (alias)")
    track_name: str | None = Field(default=None, description="Readable track title when available")
    artist_name: str | None = Field(default=None, description="Readable artist name when available")
    strategy: str = Field(default="hybrid", description="Recommendation strategy (hybrid, collaborative, content_based, cold_start_popularity)")
    reason: str | None = Field(default=None, description="Explanation for this recommendation")


class RecommendationResponse(BaseModel):
    user_id: str
    strategy: str = Field(default="hybrid", description="Strategy used: hybrid, collaborative, content_based, or cold_start_popularity")
    count: int
    recommendations: list[RecommendationItem]
    weights_used: dict[str, float] | None = Field(default=None, description="Weights used in hybrid formula")
    source: str = Field(default="Apache Mahout + Behavioral Hybrid Engine", description="Provenance of recommendations")
    execution_time_ms: float = Field(default=0.0, description="Serving latency in milliseconds")


class SimilarSongItem(BaseModel):
    rank: int
    item_id: str
    similarity_score: float
    song_code: str | None = None
    track_name: str | None = None
    artist_name: str | None = None
    similarity_type: str = "Interaction Co-occurrence"


class SimilarSongsResponse(BaseModel):
    query_item_id: str
    query_song_code: str | None = None
    count: int
    similar_songs: list[SimilarSongItem]


class SongDetail(BaseModel):
    item_id: str
    song_code: str | None = None
    total_plays: int = 0
    unique_listeners: int = 0
    track_name: str | None = None
    artist_name: str | None = None
    track_mbid: str | None = None
    artist_mbid: str | None = None
    popularity_rank: int | None = None


class UserHistoryItem(BaseModel):
    item_id: str
    song_code: str | None = None
    play_count: int = 1
    track_name: str | None = None
    artist_name: str | None = None


class UserHistoryResponse(BaseModel):
    user_id: str
    total_interactions: int
    history: list[UserHistoryItem]


class LiveEventRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="User ID (e.g. 1, 2, 3...)")
    song_id: str | None = Field(default=None, description="Song/Item ID (e.g. 103, 21666...)")
    item_id: str | None = Field(default=None, description="Alternative item identifier")
    event_type: Literal["play", "skip", "like", "replay"] = Field(
        default="play", description="Event type: play, skip, like, replay"
    )
    action: str | None = Field(default=None, description="Alternative action field")
    duration_seconds: int = Field(default=180, ge=0, le=86400, description="Listening duration in seconds")

    def get_effective_song_id(self) -> str:
        return self.song_id or self.item_id or "1"

    def get_effective_event_type(self) -> str:
        return self.event_type if self.event_type != "play" or not self.action else self.action


class LiveEventResponse(BaseModel):
    status: str
    event_id: str
    message: str
    event: dict[str, Any] | None = None
    logged_event: dict[str, Any] | None = None


class LiveStatsResponse(BaseModel):
    total_events_processed: int
    buffered_events_count: int
    unique_active_users: int
    event_type_distribution: dict[str, int]
    top_trending_recent_songs: list[dict[str, Any]]
    simulator_active: bool
    last_event_timestamp: str | None = None


class EvaluationMetricsResponse(BaseModel):
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


class HealthResponse(BaseModel):
    status: str
    mahout_data_available: bool = True
    mongodb_available: bool = False
    hadoop_hdfs: str = "Configured (runtime not probed)"
    spark_engine: str = "Configured (runtime not probed)"
    mahout_cf: str = "Loaded (Item-Based CF / LogLikelihood)"
    mongodb_status: str = "Unavailable until MongoDB is reachable"
    active_recommendation_count: int = 0
    catalog_items_count: int = 0
    dataset_interactions_count: int = 0
    timestamp: str | None = None


class InfoResponse(BaseModel):
    project: str
    student: str
    prn: str
    backend: str
    recommendation_strategies: list[str]
    hybrid_formula: str
    notes: list[str]


class MongoStatsResponse(BaseModel):
    status: str
    database: str
    recommendations_count: int
    songs_count: int
    events_count: int


# Backward compatibility aliases
Recommendation = RecommendationItem
EventRequest = LiveEventRequest
EventResponse = LiveEventResponse
