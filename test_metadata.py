import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from metadata_test import (
    Clip,
    build_plan,
    file_scanner,
    get_destination,
    metadata_reader,
    organize_clips,
    parse_creation_time,
    sanitize_folder_name,
)


class SanitizationTests(unittest.TestCase):
    def test_removes_invalid_and_zero_width_characters(self) -> None:
        self.assertEqual(sanitize_folder_name(" My\u200b:Game? "), "MyGame")

    def test_rejects_empty_and_reserved_names(self) -> None:
        self.assertIsNone(sanitize_folder_name("..."))
        self.assertIsNone(sanitize_folder_name("CON.txt"))


class MetadataReaderTests(unittest.TestCase):
    @patch("metadata_test.subprocess.run")
    def test_reads_title_and_creation_time(self, run: object) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps({"format": {"tags": {"title": "Game", "creation_time": "2024-06-08T19:15:14Z"}}}), ""
        )
        game, created, error = metadata_reader(Path("clip.mp4"))
        self.assertEqual(game, "Game")
        self.assertEqual(created.year, 2024)
        self.assertIsNone(error)

    @patch("metadata_test.subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30))
    def test_timeout_becomes_a_per_file_error(self, _run: object) -> None:
        game, created, error = metadata_reader(Path("clip.mp4"))
        self.assertIsNone(game)
        self.assertIsNone(created)
        self.assertIn("timed out", error)


class MetadataParsingTests(unittest.TestCase):
    def test_parses_utc_creation_time(self) -> None:
        self.assertEqual(parse_creation_time("2024-06-08T19:15:14Z").year, 2024)

    def test_invalid_creation_time_is_unknown(self) -> None:
        self.assertIsNone(parse_creation_time("not a date"))


class ScannerTests(unittest.TestCase):
    @patch("metadata_test.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_skips_the_organized_output_folder(self, _reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.mp4").touch()
            output = root / "Organized"
            output.mkdir()
            (output / "already-organized.mp4").touch()
            clips = file_scanner(root, output)
        self.assertEqual([clip.path.name for clip in clips], ["source.mp4"])


class PlanAndMoveTests(unittest.TestCase):
    def test_missing_game_goes_to_unsorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = Clip(root / "renamed video.mp4", None, 2024)
            destination = get_destination(clip, root / "Organized")
            self.assertEqual(destination, root / "Organized" / "Unsorted" / "renamed video.mp4")

    def test_duplicate_destinations_are_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = [
                Clip(root / "one" / "clip.mp4", "Game", 2024),
                Clip(root / "two" / "clip.mp4", "Game", 2024),
            ]
            plan = build_plan(clips, root / "Organized")
        self.assertTrue(all(move.status.startswith("CONFLICT") for move in plan))

    def test_moves_a_ready_file_and_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            plan = build_plan([Clip(source, "Game", 2024)], root / "Organized")
            progress = []
            messages = organize_clips(plan, lambda *event: progress.append(event), echo=False)
            destination = root / "Organized" / "Game" / "2024" / "clip.mp4"
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_bytes(), b"video")
        self.assertEqual(messages, ["MOVED: clip.mp4"])
        self.assertEqual(len(progress), 1)

    def test_rechecks_destination_before_moving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"source")
            plan = build_plan([Clip(source, "Game", 2024)], root / "Organized")
            destination = plan[0].destination
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"existing")
            messages = organize_clips(plan, echo=False)
            self.assertTrue(source.exists())
            self.assertEqual(destination.read_bytes(), b"existing")
        self.assertEqual(messages, ["SKIPPED: clip.mp4 (destination now exists)"])


if __name__ == "__main__":
    unittest.main()
