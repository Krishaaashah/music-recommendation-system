import tempfile
import unittest
from pathlib import Path

from backend.recommendation_service import RecommendationService, parse_recommendation_lines
from backend.event_service import EventService


class RecommendationParserTests(unittest.TestCase):
    def test_parses_mahout_vector_output(self) -> None:
        lines = ["1\t[103:7.036205,21666:7.031693,33:7.0279803]"]

        parsed = list(parse_recommendation_lines(lines))

        self.assertEqual(parsed[0][0], "1")
        self.assertEqual(parsed[0][1][0].item_id, "103")
        self.assertAlmostEqual(parsed[0][1][0].score, 7.036205)

    def test_parses_csv_output(self) -> None:
        lines = ["2,83100,2.5091124"]

        parsed = list(parse_recommendation_lines(lines))

        self.assertEqual(parsed[0][0], "2")
        self.assertEqual(parsed[0][1][0].item_id, "83100")
        self.assertAlmostEqual(parsed[0][1][0].score, 2.5091124)

    def test_service_reads_part_files_and_limits_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "part-r-00000").write_text(
                "1\t[10:1.0,20:3.0,30:2.0]\n2\t[99:9.0]\n",
                encoding="utf-8",
            )
            (output_dir / "_SUCCESS").write_text("", encoding="utf-8")

            service = RecommendationService(output_dir)
            recommendations = service.get_recommendations("1", limit=2)

        self.assertIsNotNone(recommendations)
        self.assertEqual([item.item_id for item in recommendations], ["20", "30"])

    def test_song_mapping_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "part-r-00000").write_text("1\t[103:7.036205]\n", encoding="utf-8")
            mapping_file = output_dir / "song_mapping.csv"
            mapping_file.write_text("SOAKIMP12A8C130995,103\n", encoding="utf-8")

            service = RecommendationService(output_dir, song_mapping_path=mapping_file)
            recs = service.get_recommendations("1", limit=1)

        self.assertIsNotNone(recs)
        self.assertEqual(recs[0].song_id, "SOAKIMP12A8C130995")

    def test_content_recommendations_use_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "part-r-00000").write_text("1\t[10:1.0]\n", encoding="utf-8")
            mapping = root / "song_mapping.csv"
            mapping.write_text("artist-a-track,10\nartist-a-related,20\n", encoding="utf-8")
            users = root / "user_mapping.csv"
            users.write_text("user-a,1\n", encoding="utf-8")
            dataset = root / "train_triplets.txt"
            dataset.write_text("user-a\tartist-a-track\t3\n", encoding="utf-8")
            metadata = root / "song_metadata.csv"
            metadata.write_text(
                "item_id,track_key,artist_name,track_name,artist_mbid,track_mbid,total_plays,unique_listeners\n"
                "10,key10,Artist A,First Song,,,3,1\n"
                "20,key20,Artist A,Second Song,,,2,1\n",
                encoding="utf-8",
            )
            service = RecommendationService(
                output_dir,
                song_mapping_path=mapping,
                user_mapping_path=users,
                dataset_path=dataset,
                song_metadata_path=metadata,
            )
            content = service.get_content_recommendations("1", limit=1)

        self.assertEqual(len(content), 1)
        self.assertEqual(content[0].item_id, "20")
        self.assertEqual(content[0].strategy, "content_based")

    def test_content_simulator_event_is_published_for_spark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = EventService(stream_input_dir=Path(temp_dir))
            event = service.record_event("1", "103", "play")
            event_file = Path(temp_dir) / f"{event.event_id}.json"
            self.assertTrue(event_file.is_file())


if __name__ == "__main__":
    unittest.main()
