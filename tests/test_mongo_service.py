import unittest
from unittest.mock import MagicMock, patch

from backend.mongo_service import MongoService


class MongoServiceUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MongoService(uri="mongodb://mock:27017", db_name="test_db")

    @patch("backend.mongo_service.MongoClient")
    def test_is_available_returns_true_on_success(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client_cls.return_value = mock_client

        service = MongoService()
        self.assertTrue(service.is_available())

    @patch("backend.mongo_service.MongoClient")
    def test_get_recommendations_returns_formatted_list(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_db.recommendations.find_one.return_value = {
            "user_id": "1",
            "recommendations": [
                {"item_id": "103", "score": 7.036205},
                {"item_id": "21666", "score": 7.031693},
            ],
        }
        mock_client_cls.return_value = mock_client

        service = MongoService()
        recs = service.get_recommendations("1", limit=1)
        self.assertIsNotNone(recs)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["item_id"], "103")

    @patch("backend.mongo_service.MongoClient")
    def test_unknown_user_returns_none(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_db.recommendations.find_one.return_value = None
        mock_client_cls.return_value = mock_client

        service = MongoService()
        self.assertIsNone(service.get_recommendations("nonexistent"))


if __name__ == "__main__":
    unittest.main()
