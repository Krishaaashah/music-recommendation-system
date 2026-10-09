import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.recommendation_service import RecommendationService


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_service = main_module.recommendation_service
        self.original_mongo = main_module.mongo_service
        self.client = TestClient(main_module.app)

    def tearDown(self) -> None:
        main_module.recommendation_service = self.original_service
        main_module.mongo_service = self.original_mongo

    def test_home_endpoint(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("docs", response.json())
        self.assertIn("health", response.json())

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("mahout_data_available", payload)
        self.assertIn("mongodb_available", payload)

    def test_api_info_endpoint(self) -> None:
        response = self.client.get("/api/info")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project"], "Scalable Real-Time Music Recommendation System")
        self.assertIsInstance(payload["notes"], list)

    def test_recommend_endpoint_uses_real_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "part-r-00000").write_text(
                "1\t[103:7.036205,21666:7.031693,33:7.0279803]\n",
                encoding="utf-8",
            )
            main_module.recommendation_service = RecommendationService(output_dir)

            response = self.client.get("/recommend/1?n=2&source=mahout")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user_id"], "1")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["recommendations"][0]["item_id"], "103")

    def test_recommend_endpoint_with_mongo_mock(self) -> None:
        mock_mongo = MagicMock()
        mock_mongo.is_available.return_value = True
        mock_mongo.get_recommendations.return_value = [
            {"item_id": "103", "score": 7.036205, "song_id": "SOAKIMP12A8C130995"}
        ]
        mock_mongo.get_song_mapping.return_value = "SOAKIMP12A8C130995"
        main_module.mongo_service = mock_mongo

        response = self.client.get("/recommend/1?n=1&source=mongodb")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "mongodb")
        self.assertEqual(payload["recommendations"][0]["item_id"], "103")
        self.assertEqual(payload["recommendations"][0]["song_id"], "SOAKIMP12A8C130995")

    def test_unknown_user_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "part-r-00000").write_text("1\t[103:7.036205]\n", encoding="utf-8")
            main_module.recommendation_service = RecommendationService(output_dir)

            response = self.client.get("/recommend/missing?source=mahout")

        self.assertEqual(response.status_code, 404)

    def test_event_logging_endpoint(self) -> None:
        mock_mongo = MagicMock()
        mock_mongo.is_available.return_value = True
        mock_mongo.log_interaction.return_value = True
        main_module.mongo_service = mock_mongo

        response = self.client.post("/events", json={"user_id": "1", "item_id": "103", "action": "listen"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], ["success", "recorded"])


if __name__ == "__main__":
    unittest.main()
