import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from dev_flatten_videos import build_flatten_plan, flatten_videos
from operation_history import MoveRecord, save_last_operation, undo_last_operation
from organizer import (
    Clip,
    build_plan,
    file_scanner,
    get_destination,
    metadata_reader,
    organize_clips,
    parse_creation_time,
    ScanCancelled,
    sanitize_folder_name,
)


class SanitizationTests(unittest.TestCase):
    def test_removes_invalid_and_zero_width_characters(self) -> None:
        self.assertEqual(sanitize_folder_name(" My\u200b:Game? "), "MyGame")

    def test_rejects_empty_and_reserved_names(self) -> None:
        self.assertIsNone(sanitize_folder_name("..."))
        self.assertIsNone(sanitize_folder_name("CON.txt"))


class MetadataReaderTests(unittest.TestCase):
    @patch("organizer.subprocess.run")
    def test_reads_title_and_creation_time(self, run: object) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps({"format": {"tags": {"title": "Game", "creation_time": "2024-06-08T19:15:14Z"}}}), ""
        )
        game, created, error = metadata_reader(Path("clip.mp4"))
        self.assertEqual(game, "Game")
        self.assertEqual(created.year, 2024)
        self.assertIsNone(error)

    @patch("organizer.subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30))
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
    @patch("organizer.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_skips_the_organized_output_folder(self, _reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.mp4").touch()
            output = root / "Organized"
            output.mkdir()
            (output / "already-organized.mp4").touch()
            clips = file_scanner(root, output)
        self.assertEqual([clip.path.name for clip in clips], ["source.mp4"])

    @patch("organizer.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_scans_with_workers_and_keeps_paths_sorted(self, _reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zulu.mp4").touch()
            (root / "alpha.mp4").touch()
            progress = []
            clips = file_scanner(root, root / "Organized", lambda *event: progress.append(event), workers=2)
        self.assertEqual([clip.path.name for clip in clips], ["alpha.mp4", "zulu.mp4"])
        self.assertEqual(sorted(event[0] for event in progress), [1, 2])
        self.assertTrue(all(event[1] == 2 for event in progress))

    @patch("organizer.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_reuses_cached_metadata_for_an_unchanged_file(self, reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clip.mp4").touch()
            cache_path = root / "cache.json"
            file_scanner(root, root / "Organized", cache_path=cache_path)
            file_scanner(root, root / "Organized", cache_path=cache_path)
        self.assertEqual(reader.call_count, 1)

    def test_can_cancel_before_metadata_reads_begin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clip.mp4").touch()
            with self.assertRaises(ScanCancelled):
                file_scanner(root, root / "Organized", cancelled=lambda: True, cache_path=None)


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

    def test_case_only_destination_difference_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = [
                Clip(root / "one" / "clip.mp4", "Game", 2024),
                Clip(root / "two" / "CLIP.mp4", "Game", 2024),
            ]
            plan = build_plan(clips, root / "Organized")
        self.assertTrue(all(move.status.startswith("CONFLICT") for move in plan))

    def test_can_safely_rename_duplicate_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = [
                Clip(root / "one" / "clip.mp4", "Game", 2024),
                Clip(root / "two" / "clip.mp4", "Game", 2024),
            ]
            plan = build_plan(clips, root / "Organized", rename_duplicates=True)
        self.assertEqual([move.destination.name for move in plan], ["clip.mp4", "clip (2).mp4"])
        self.assertTrue(all(move.status == "READY" for move in plan))

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


class FlattenTests(unittest.TestCase):
    def test_flattens_nested_video_and_renames_a_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_video = root / "clip.mp4"
            root_video.write_bytes(b"root")
            nested_video = root / "Organized" / "Game" / "2024" / "clip.mp4"
            nested_video.parent.mkdir(parents=True)
            nested_video.write_bytes(b"nested")

            plan = build_flatten_plan(root)
            self.assertEqual(plan[0][1].name, "clip (2).mp4")
            messages = flatten_videos(plan, echo=False)

            self.assertEqual(root_video.read_bytes(), b"root")
            self.assertEqual((root / "clip (2).mp4").read_bytes(), b"nested")
        self.assertEqual(messages, ["MOVED: clip.mp4 -> clip (2).mp4"])


class UndoTests(unittest.TestCase):
    def test_undo_returns_recorded_file_without_overwriting_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "original" / "clip.mp4"
            destination = root / "Organized" / "Game" / "2024" / "clip.mp4"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"video")
            state_directory = root / "state"
            journal_path = state_directory / "last-operation.json"
            with patch("operation_history.STATE_DIRECTORY", state_directory), patch("operation_history.LAST_OPERATION_PATH", journal_path):
                save_last_operation("organize", [MoveRecord(source, destination)])
                messages, remaining = undo_last_operation()
            self.assertEqual(source.read_bytes(), b"video")
            self.assertFalse(destination.exists())
            self.assertIsNone(remaining)
        self.assertEqual(messages, ["UNDONE: clip.mp4 -> clip.mp4"])

    @patch("organizer.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_scan_plan_move_and_undo_work_together(self, _reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            state_directory = root / "state"
            journal_path = state_directory / "last-operation.json"
            clips = file_scanner(root, root / "Organized", cache_path=None)
            plan = build_plan(clips, root / "Organized")
            moves: list[MoveRecord] = []
            organize_clips(plan, on_moved=lambda old, new: moves.append(MoveRecord(old, new)), echo=False)
            with patch("operation_history.STATE_DIRECTORY", state_directory), patch("operation_history.LAST_OPERATION_PATH", journal_path):
                save_last_operation("organize", moves)
                _messages, remaining = undo_last_operation()
            self.assertTrue(source.exists())
            self.assertIsNone(remaining)


class FlattenSafetyTests(unittest.TestCase):
    def test_rechecks_flatten_destination_before_moving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested_video = root / "nested" / "clip.mp4"
            nested_video.parent.mkdir()
            nested_video.write_bytes(b"nested")

            plan = build_flatten_plan(root)
            planned_destination = plan[0][1]
            planned_destination.write_bytes(b"newer root file")
            messages = flatten_videos(plan, echo=False)

            self.assertEqual(planned_destination.read_bytes(), b"newer root file")
            self.assertEqual((root / "clip (2).mp4").read_bytes(), b"nested")
        self.assertEqual(messages, ["MOVED: clip.mp4 -> clip (2).mp4"])


if __name__ == "__main__":
    unittest.main()
