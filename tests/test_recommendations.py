from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.recommendation_service import (
    RecommendationService,
    ScoredItem,
    parse_recommendation_lines,
)
from backend.event_service import EventService
from backend.evaluation_service import EvaluationService


class RecommendationServiceTests(unittest.TestCase):
    def test_parse_mahout_vector_line(self):
        sample_line = "1\t[103:7.036205,21666:7.031693,33:7.0279803]"
        parsed = list(parse_recommendation_lines([sample_line]))
        self.assertEqual(len(parsed), 1)
        user_id, items = parsed[0]
        self.assertEqual(user_id, "1")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].item_id, "103")
        self.assertAlmostEqual(items[0].score, 7.036205, places=5)

    def test_parse_csv_line(self):
        sample_line = "2,83100,2.5091124"
        parsed = list(parse_recommendation_lines([sample_line]))
        self.assertEqual(len(parsed), 1)
        user_id, items = parsed[0]
        self.assertEqual(user_id, "2")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_id, "83100")
        self.assertAlmostEqual(items[0].score, 2.5091124, places=5)

    def test_hybrid_recommendation_computation(self):
        service = RecommendationService()
        strategy, items, weights = service.get_hybrid_recommendations("1", limit=5)
        self.assertEqual(strategy, "hybrid")
        self.assertGreater(len(items), 0)
        self.assertLessEqual(len(items), 5)
        self.assertIsNotNone(items[0].song_code)
        self.assertIn("Hybrid Match", items[0].reason)

    def test_cold_start_popularity_fallback(self):
        service = RecommendationService()
        strategy, items, weights = service.get_hybrid_recommendations("unknown_user_999999", limit=5)
        self.assertEqual(strategy, "cold_start_popularity")
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0].strategy, "cold_start_popularity")

    def test_similar_songs_lookup(self):
        service = RecommendationService()
        sim_songs = service.get_similar_songs("103", limit=5)
        self.assertGreater(len(sim_songs), 0)
        self.assertEqual(sim_songs[0]["rank"], 1)
        self.assertIn("similarity_score", sim_songs[0])


class EventServiceTests(unittest.TestCase):
    def test_record_and_buffer_event(self):
        service = EventService()
        event = service.record_event("1", "103", "play", duration_seconds=180)
        self.assertEqual(event.user_id, "1")
        self.assertEqual(event.song_id, "103")
        self.assertEqual(event.event_type, "play")

        recent = service.get_recent_events(limit=10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["event_id"], event.event_id)

        stats = service.get_stats()
        self.assertEqual(stats["total_events_processed"], 1)
        self.assertEqual(stats["unique_active_users"], 1)


class EvaluationServiceTests(unittest.TestCase):
    def test_evaluation_metrics_integrity(self):
        eval_service = EvaluationService()
        metrics = eval_service.get_metrics()
        self.assertEqual(metrics.k, 10)
        self.assertGreater(metrics.hit_rate_at_k, 0.0)
        self.assertGreater(metrics.mrr_at_k, 0.0)
        self.assertEqual(metrics.evaluated_users_count, 20729)
        self.assertGreaterEqual(metrics.map_at_k, 0.0)
        self.assertGreaterEqual(metrics.ndcg_at_k, 0.0)


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student"], "Kresha Shah")
        self.assertEqual(data["prn"], "24070126512")

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn("hadoop_hdfs", data)

    def test_recommend_hybrid_user_1(self):
        resp = self.client.get("/recommend/1?n=5&strategy=hybrid")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_id"], "1")
        self.assertEqual(data["strategy"], "hybrid")
        self.assertEqual(len(data["recommendations"]), 5)
        self.assertEqual(data["recommendations"][0]["item_id"], "103")

    def test_recommend_collaborative_unknown_user_404(self):
        resp = self.client.get("/recommend/99999999?strategy=collaborative")
        self.assertEqual(resp.status_code, 404)

    def test_similar_songs_endpoint(self):
        resp = self.client.get("/similar/103?n=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["query_item_id"], "103")
        self.assertEqual(len(data["similar_songs"]), 5)

    def test_evaluation_metrics_endpoint(self):
        resp = self.client.get("/evaluation/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["k"], 10)
        self.assertEqual(data["evaluated_users_count"], 20729)

    def test_content_strategy_reports_missing_metadata(self):
        resp = self.client.get("/recommend/1?strategy=content_based")
        self.assertEqual(resp.status_code, 501)

    def test_invalid_catalog_event_returns_404(self):
        resp = self.client.post("/events", json={"user_id": "1", "song_id": "does-not-exist"})
        self.assertEqual(resp.status_code, 404)

    def test_live_event_flow(self):
        post_resp = self.client.post("/events", json={"user_id": "1", "song_id": "103", "event_type": "like"})
        self.assertEqual(post_resp.status_code, 200)

        get_resp = self.client.get("/live/events?limit=5")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertGreater(data["count"], 0)


if __name__ == "__main__":
    unittest.main()
