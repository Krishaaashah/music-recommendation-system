from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from backend.evaluation_service import EvaluationService
from backend.event_service import EventService
from backend.models import (
    EvaluationMetricsResponse,
    HealthResponse,
    InfoResponse,
    LiveEventRequest,
    LiveEventResponse,
    LiveStatsResponse,
    MongoStatsResponse,
    RecommendationItem,
    RecommendationResponse,
    SimilarSongItem,
    SimilarSongsResponse,
    SongDetail,
    UserHistoryItem,
    UserHistoryResponse,
)
from backend.mongo_service import MongoService
from backend.recommendation_service import (
    RecommendationDataUnavailable,
    RecommendationService,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MusicRecommendationAPI")

recommendation_service = RecommendationService()
mongo_service = MongoService()
evaluation_service = EvaluationService()
event_service = EventService(
    mongo_persister=lambda evt: mongo_service.log_interaction(
        evt.get("user_id", ""),
        evt.get("song_id", ""),
        action=evt.get("event_type", "play"),
    )
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Initializing Big Data Music Recommendation API...")
    if recommendation_service.source_available:
        try:
            logger.info("Pre-warming recommendation caches and song mappings...")
            recommendation_service._load_mappings()
            event_service.set_song_lookup(recommendation_service.get_song_code)
            event_service.set_sample_catalog(
                recommendation_service.known_user_ids(),
                recommendation_service.known_item_ids(),
            )
            if os.getenv("SONG_METADATA_PATH"):
                recommendation_service._load_song_metadata()
        except Exception as exc:
            logger.warning("Cache pre-warming notice: %s", exc)

    if mongo_service.is_available():
        logger.info("Connected to MongoDB at %s. Ensuring indexes...", mongo_service.uri)
        mongo_service.ensure_indexes()
    else:
        logger.info("MongoDB is not reachable at %s. Running in standalone fallback mode.", mongo_service.uri)

    yield
    # Shutdown sequence
    event_service.stop_simulator()
    logger.info("Music Recommendation API shutdown complete.")


app = FastAPI(
    title="Scalable Real-Time Music Recommendation API",
    description=(
        "Enterprise-grade Big Data recommendation platform utilizing Apache Hadoop HDFS, "
        "Apache Spark, Apache Mahout Item-Based Collaborative Filtering (SIMILARITY_LOGLIKELIHOOD), "
        "MongoDB NoSQL Document Store, and Real-Time Event Stream Ingestion."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _recommendation_item(
    rank: int,
    item_id: str,
    score: float,
    song_code: str | None,
    strategy: str,
    reason: str | None,
) -> RecommendationItem:
    metadata = recommendation_service.get_song_metadata(str(item_id))
    return RecommendationItem(
        rank=rank,
        item_id=str(item_id),
        score=float(score),
        song_code=song_code,
        song_id=song_code,
        track_name=metadata.get("track_name"),
        artist_name=metadata.get("artist_name"),
        strategy=strategy,
        reason=reason,
    )


@app.get("/", tags=["System"])
def root() -> dict[str, Any]:
    return {
        "title": "Scalable Real-Time Music Recommendation System",
        "student": "Kresha Shah",
        "prn": "24070126512",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health",
        "docs_url": "/docs",
        "health_url": "/health",
        "endpoints": {
            "personalized_recommendations": "/recommend/{user_id}?n=10&strategy=hybrid",
            "similar_songs": "/similar/{song_id}?n=10",
            "song_info": "/songs/{song_id}",
            "user_history": "/user/{user_id}/history",
            "live_events_stream": "/live/events",
            "live_streaming_stats": "/live/stats",
            "evaluation_metrics": "/evaluation/metrics",
            "mongodb_stats": "/mongo/stats",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    mongo_ok = mongo_service.is_available()
    rec_available = recommendation_service.source_available
    return HealthResponse(
        status="healthy" if rec_available else "degraded",
        mahout_data_available=rec_available,
        mongodb_available=mongo_ok,
        hadoop_hdfs="Configured (Docker roles: h-primary, h-worker1..h-worker5; runtime not probed)",
        spark_engine="Configured (Apache Spark 3.5.9; runtime not probed)",
        mahout_cf=f"Loaded ({recommendation_service.recommendation_user_count:,} users; Item-Based CF / SIMILARITY_LOGLIKELIHOOD)",
        mongodb_status="Connected (Port 27017)" if mongo_ok else "Standalone Cache Mode (MongoDB offline)",
        active_recommendation_count=recommendation_service.recommendation_user_count if rec_available else 0,
        catalog_items_count=recommendation_service.catalog_item_count,
        dataset_interactions_count=recommendation_service.dataset_interaction_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/info", response_model=InfoResponse, tags=["System"])
def info() -> InfoResponse:
    dataset_label = "Last.fm 1K" if "lastfm" in str(recommendation_service.dataset_path or "").lower() else "Echo Nest Taste Profile"
    return InfoResponse(
        project="Scalable Real-Time Music Recommendation System",
        student="Kresha Shah",
        prn="24070126512",
        backend="FastAPI / Python 3.11",
        recommendation_strategies=[
            "Hybrid Fusion (Collaborative + Content Similarity + Popularity)",
            "Collaborative Filtering (Apache Mahout Log-Likelihood Ratio)",
            "Metadata Content Similarity (artist and track title)",
            "Behavioral Item Co-occurrence (fallback from interaction history)",
            "Global Popularity (Cold-Start Fallback)",
        ],
        hybrid_formula="Score = alpha * Norm_CF + beta * Content_Similarity + gamma * Popularity",
        notes=[
            f"Processes the configured {dataset_label} interaction catalog with real user-song events.",
            "Apache Mahout 0.13.0 generates Top-N Item-Based recommendations offline on Hadoop.",
            "MongoDB stores semi-structured documents for indexed point retrieval when connected.",
            "Spark Structured Streaming processes near-real-time event files with checkpoints.",
        ],
    )


@app.get("/recommend/{user_id}", response_model=RecommendationResponse, tags=["Recommendations"])
def get_recommendations(
    user_id: str,
    n: int = Query(default=10, ge=1, le=50, description="Number of recommendations to return"),
    strategy: str = Query(
        default="hybrid",
        pattern="^(hybrid|collaborative|content_based|popularity|auto)$",
        description="Strategy: hybrid, collaborative, content_based, popularity, or auto",
    ),
    source: str | None = Query(
        default=None,
        description="Source override: 'mahout' or 'mongodb'",
    ),
    alpha: float = Query(default=0.7, ge=0.0, le=1.0, description="Collaborative Filtering weight"),
        beta: float = Query(default=0.2, ge=0.0, le=1.0, description="Behavioral co-occurrence weight"),
    gamma: float = Query(default=0.1, ge=0.0, le=1.0, description="Popularity weight"),
) -> RecommendationResponse:
    start_time = time.perf_counter()
    u_id = user_id.strip()

    try:
        if source == "mongodb":
            mongo_recs = mongo_service.get_recommendations(u_id, limit=n)
            if mongo_recs is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{u_id}' not found in MongoDB")
            recs = [
                _recommendation_item(
                    rank=idx + 1,
                    item_id=str(it.get("item_id")),
                    score=float(it.get("score", 0.0)),
                    song_code=it.get("song_code") or it.get("song_id"),
                    strategy="mongodb_cached",
                    reason="Stored MongoDB document lookup",
                )
                for idx, it in enumerate(mongo_recs)
            ]
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return RecommendationResponse(
                user_id=u_id,
                strategy="mongodb",
                count=len(recs),
                recommendations=recs,
                source="mongodb",
                execution_time_ms=elapsed_ms,
            )

        if strategy == "content_based":
            content_items = recommendation_service.get_content_recommendations(u_id, limit=n)
            if not content_items:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No content-based recommendations are available for user '{u_id}'.",
                )
            used_strategy = "content_based"
            recs = [
                _recommendation_item(
                    rank=idx + 1,
                    item_id=it.item_id,
                    score=round(it.score, 6),
                    song_code=it.song_code,
                    strategy="content_based",
                    reason=it.reason,
                )
                for idx, it in enumerate(content_items)
            ]
            weights = None

        if strategy == "popularity":
            popular_items = recommendation_service.get_popular_recommendations(limit=n)
            recs = [
                _recommendation_item(
                    rank=idx + 1,
                    item_id=it.item_id,
                    score=round(it.score, 6),
                    song_code=it.song_code,
                    strategy="popularity",
                    reason=it.reason,
                )
                for idx, it in enumerate(popular_items)
            ]
            used_strategy = "popularity"
            weights = None
        elif strategy == "collaborative" or source == "mahout":
            cf_items = recommendation_service.get_collaborative_recommendations(u_id, limit=n)
            if cf_items is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No collaborative filtering history for user '{u_id}'.",
                )
            used_strategy = "collaborative"
            recs = [
                _recommendation_item(
                    rank=idx + 1,
                    item_id=it.item_id,
                    score=round(it.score, 6),
                    song_code=it.song_code,
                    strategy="collaborative",
                    reason=it.reason,
                )
                for idx, it in enumerate(cf_items)
            ]
            weights = None
        else:
            # Hybrid or Auto strategy (with cold-start handling)
            used_strategy, scored_items, weights = recommendation_service.get_hybrid_recommendations(
                u_id, limit=n, alpha=alpha, beta=beta, gamma=gamma
            )
            recs = [
                _recommendation_item(
                    rank=idx + 1,
                    item_id=it.item_id,
                    score=round(it.score, 6),
                    song_code=it.song_code,
                    strategy=it.strategy,
                    reason=it.reason,
                )
                for idx, it in enumerate(scored_items)
            ]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return RecommendationResponse(
            user_id=u_id,
            strategy=used_strategy,
            count=len(recs),
            recommendations=recs,
            weights_used=weights,
                source="Apache Mahout 0.13.0 + Behavioral Hybrid Engine",
            execution_time_ms=elapsed_ms,
        )
    except RecommendationDataUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@app.get("/similar/{song_id}", response_model=SimilarSongsResponse, tags=["Recommendations"])
def get_similar_songs(
    song_id: str,
    n: int = Query(default=10, ge=1, le=50, description="Number of similar songs to return"),
) -> SimilarSongsResponse:
    s_id = song_id.strip()
    sim_data = recommendation_service.get_similar_songs(s_id, limit=n)
    query_code = recommendation_service.get_song_code(s_id)
    items = [
        SimilarSongItem(
            rank=it["rank"],
            item_id=it["item_id"],
            similarity_score=it["similarity_score"],
            song_code=it["song_code"],
            track_name=recommendation_service.get_song_metadata(it["item_id"]).get("track_name"),
            artist_name=recommendation_service.get_song_metadata(it["item_id"]).get("artist_name"),
            similarity_type=it["similarity_type"],
        )
        for it in sim_data
    ]
    return SimilarSongsResponse(
        query_item_id=s_id,
        query_song_code=query_code,
        count=len(items),
        similar_songs=items,
    )


@app.get("/songs/{song_id}", response_model=SongDetail, tags=["Catalog"])
def get_song_info(song_id: str) -> SongDetail:
    s_id = song_id.strip()
    detail = recommendation_service.get_song_detail(s_id)
    return SongDetail(
        item_id=s_id,
        song_code=detail.get("song_code"),
        total_plays=detail.get("total_plays", 0),
        unique_listeners=detail.get("unique_listeners", 0),
        track_name=detail.get("track_name"),
        artist_name=detail.get("artist_name"),
        track_mbid=detail.get("track_mbid"),
        artist_mbid=detail.get("artist_mbid"),
    )


@app.get("/user/{user_id}/history", response_model=UserHistoryResponse, tags=["Users"])
def get_user_history(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> UserHistoryResponse:
    u_id = user_id.strip()
    history = recommendation_service.get_user_history(u_id, limit=limit)
    items = [
        UserHistoryItem(
            item_id=h["item_id"],
            song_code=h.get("song_code"),
            play_count=h.get("play_count", 1),
            track_name=recommendation_service.get_song_metadata(h["item_id"]).get("track_name"),
            artist_name=recommendation_service.get_song_metadata(h["item_id"]).get("artist_name"),
        )
        for h in history
    ]
    return UserHistoryResponse(
        user_id=u_id,
        total_interactions=len(items),
        history=items,
    )


@app.post("/events", response_model=LiveEventResponse, tags=["Streaming"])
def record_event(payload: LiveEventRequest) -> LiveEventResponse:
    effective_song_id = payload.get_effective_song_id()
    if recommendation_service.get_song_code(effective_song_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song/item '{effective_song_id}' is not present in the available catalog.",
        )
    event = event_service.record_event(
        user_id=payload.user_id,
        song_id=effective_song_id,
        event_type=payload.event_type,
        duration_seconds=payload.duration_seconds,
    )
    return LiveEventResponse(
        status="recorded",
        event_id=event.event_id,
        message=f"Live {event.event_type} event recorded for User {event.user_id} -> Song {event.song_id}",
        event=event.to_dict(),
    )


@app.get("/live/events", tags=["Streaming"])
def get_live_events(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    events = event_service.get_recent_events(limit=limit)
    return {
        "count": len(events),
        "events": events,
    }


@app.get("/live/stats", response_model=LiveStatsResponse, tags=["Streaming"])
def get_live_stats() -> LiveStatsResponse:
    stats = event_service.get_stats()
    return LiveStatsResponse(**stats)


@app.post("/live/simulator/start", tags=["Streaming"])
def start_event_simulator(
    interval_seconds: float = Query(default=2.0, ge=0.2, le=10.0),
) -> dict[str, Any]:
    try:
        event_service.start_simulator(interval_seconds=interval_seconds)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return {
        "status": "active",
        "message": f"Real-time event simulator started with interval {interval_seconds}s",
    }


@app.post("/live/simulator/stop", tags=["Streaming"])
def stop_event_simulator() -> dict[str, Any]:
    event_service.stop_simulator()
    return {
        "status": "stopped",
        "message": "Real-time event simulator stopped",
    }


@app.get("/evaluation/metrics", response_model=EvaluationMetricsResponse, tags=["Evaluation"])
def get_evaluation_metrics() -> EvaluationMetricsResponse:
    metrics = evaluation_service.to_dict()
    return EvaluationMetricsResponse(**metrics)


@app.get("/mongo/stats", response_model=MongoStatsResponse, tags=["MongoDB NoSQL"])
def get_mongo_stats() -> MongoStatsResponse:
    stats = mongo_service.get_stats()
    return MongoStatsResponse(
        status=stats["status"],
        database=stats["database"],
        recommendations_count=stats["recommendations_count"],
        songs_count=stats["songs_count"],
        events_count=stats["events_count"],
    )


@app.get("/mongo/recommend/{user_id}", tags=["MongoDB NoSQL"])
def get_mongo_recommendations(user_id: str, limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    doc = mongo_service.get_recommendations(user_id, limit=limit)
    if not doc:
        # Fallback to recommendation service
        cf_items = recommendation_service.get_collaborative_recommendations(user_id, limit=limit)
        if not cf_items:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found in MongoDB or Mahout output")
        return {
            "user_id": user_id,
            "source": "fallback_mahout_parser",
            "count": len(cf_items),
            "recommendations": [
                {"item_id": it.item_id, "score": it.score, "song_code": it.song_code}
                for it in cf_items
            ],
        }
    return {
        "user_id": user_id,
        "source": "mongodb_document_store",
        "count": len(doc),
        "recommendations": doc,
    }
