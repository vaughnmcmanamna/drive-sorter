import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flatten_videos import build_flatten_plan, flatten_videos
from empty_folders import build_empty_folder_plan, remove_empty_folders
from media_tools import media_tool_path, missing_media_tools, verify_media_tools
from operation_history import MoveRecord, load_last_operation, save_last_operation, undo_last_operation
from organizer import (
    Clip,
    build_plan,
    classify_clip,
    file_scanner,
    find_unsorted_videos,
    get_destination,
    known_games,
    metadata_reader,
    organize_clips,
    parse_creation_time,
    refresh_missing_years,
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

    @patch("organizer.media_tool_path", return_value=None)
    @patch("organizer.subprocess.run")
    def test_missing_ffprobe_is_reported_without_starting_a_process(
        self, run: object, _tool: object
    ) -> None:
        game, created, error = metadata_reader(Path("clip.mp4"))
        self.assertIsNone(game)
        self.assertIsNone(created)
        self.assertIn("reinstall", error)
        run.assert_not_called()


class MediaToolTests(unittest.TestCase):
    @patch("media_tools.shutil.which", return_value=None)
    def test_prefers_a_bundled_media_tool(self, _which: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "tools" / "ffmpeg.exe"
            executable.parent.mkdir()
            executable.touch()
            with patch("media_tools.RESOURCE_DIRECTORY", root), patch("media_tools.os.name", "nt"):
                self.assertEqual(media_tool_path("ffmpeg"), executable)

    @patch("media_tools.media_tool_path", return_value=None)
    def test_reports_both_missing_release_tools(self, _tool: object) -> None:
        self.assertEqual(missing_media_tools(), ["ffmpeg", "ffprobe"])

    @patch("media_tools.media_tool_path", return_value=None)
    def test_verification_reports_missing_tools(self, _tool: object) -> None:
        self.assertEqual(verify_media_tools(), {"ffmpeg": "not found", "ffprobe": "not found"})


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

    @patch("organizer.metadata_reader")
    def test_unexpected_metadata_failure_does_not_stop_other_files(self, reader: object) -> None:
        reader.side_effect = [RuntimeError("broken reader"), ("Game", datetime(2024, 1, 1), None)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alpha.mp4").touch()
            (root / "beta.mp4").touch()
            clips = file_scanner(root, root / "Organized", workers=1, cache_path=None)
        self.assertIn("unexpectedly", clips[0].metadata_error)
        self.assertEqual(clips[1].game, "Game")

    @patch("organizer.metadata_reader", return_value=("Game", datetime(2024, 1, 1), None))
    def test_unwritable_cache_does_not_fail_the_scan(self, _reader: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clip.mp4").touch()
            blocker = root / "not-a-folder"
            blocker.write_text("file", encoding="utf-8")
            clips = file_scanner(root, root / "Organized", cache_path=blocker / "cache.json")
        self.assertEqual(clips[0].game, "Game")


class PlanAndMoveTests(unittest.TestCase):
    def test_finds_only_videos_waiting_in_unsorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Organized"
            unsorted = output / "Unsorted"
            unsorted.mkdir(parents=True)
            (unsorted / "one.mp4").touch()
            (unsorted / "notes.txt").touch()
            organized = output / "Game" / "2024" / "two.mp4"
            organized.parent.mkdir(parents=True)
            organized.touch()
            self.assertEqual(find_unsorted_videos(output), [unsorted / "one.mp4"])

    def test_can_review_and_move_a_clip_after_it_was_organized_as_unsorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "Organized"
            source = root / "clip.mp4"
            source.write_bytes(b"video")

            first_plan = build_plan([Clip(source, None, 2024)], output)
            organize_clips(first_plan, echo=False)
            unsorted_path = output / "Unsorted" / "clip.mp4"
            self.assertEqual(find_unsorted_videos(output), [unsorted_path])

            reviewed = classify_clip(Clip(unsorted_path, None, 2024), "Game")
            second_plan = build_plan([reviewed], output)
            organize_clips(second_plan, echo=False)

            self.assertFalse(unsorted_path.exists())
            self.assertEqual((output / "Game" / "2024" / "clip.mp4").read_bytes(), b"video")

    def test_manually_classifies_a_clip_without_losing_its_year(self) -> None:
        clip = Clip(Path("clip.mp4"), None, 2024, "no usable game title in metadata")
        classified = classify_clip(clip, " Valorant? ")
        self.assertEqual(classified.game, "Valorant")
        self.assertEqual(classified.year, 2024)
        self.assertIsNone(classified.metadata_error)

    def test_manual_classification_rejects_an_unsafe_game_name(self) -> None:
        with self.assertRaises(ValueError):
            classify_clip(Clip(Path("clip.mp4"), None, None), "CON")

    def test_known_games_include_scan_and_existing_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Organized"
            (output / "Halo Infinite").mkdir(parents=True)
            (output / "valorant").mkdir()
            (output / "Unsorted").mkdir()
            games = known_games([Clip(Path("clip.mp4"), "VALORANT", 2024)], output)
        self.assertEqual(games, ["Halo Infinite", "VALORANT"])

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

    def test_duplicate_renaming_also_avoids_an_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "Organized" / "Game" / "2024" / "clip.mp4"
            destination.parent.mkdir(parents=True)
            destination.touch()
            plan = build_plan(
                [Clip(root / "clip.mp4", "Game", 2024)],
                root / "Organized",
                rename_duplicates=True,
            )
        self.assertEqual(plan[0].destination.name, "clip (2).mp4")
        self.assertEqual(plan[0].status, "READY")

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

    def test_does_not_move_a_source_replaced_by_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            plan = build_plan([Clip(source, "Game", 2024)], root / "Organized")
            source.unlink()
            source.mkdir()
            messages = organize_clips(plan, echo=False)
            self.assertTrue(source.is_dir())
            self.assertFalse(plan[0].destination.exists())
        self.assertTrue(messages[0].startswith("SKIPPED:"))

    @patch("organizer.metadata_reader", return_value=(None, datetime(2022, 6, 1), None))
    def test_refreshes_year_for_a_persistent_unsorted_clip(self, _reader: object) -> None:
        clip = Clip(Path("Organized/Unsorted/clip.mp4"), None, None, "waiting")
        refreshed = refresh_missing_years([clip], workers=1)
        self.assertEqual(refreshed[0].year, 2022)
        self.assertIsNone(refreshed[0].game)


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
    @patch.object(Path, "read_text", side_effect=PermissionError("denied"))
    def test_unreadable_history_is_treated_as_unavailable(self, _read_text: object) -> None:
        self.assertIsNone(load_last_operation())

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

    def test_undo_does_not_move_a_directory_replacing_the_recorded_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "original" / "clip.mp4"
            destination = root / "Organized" / "clip.mp4"
            destination.mkdir(parents=True)
            state_directory = root / "state"
            journal_path = state_directory / "last-operation.json"
            with patch("operation_history.STATE_DIRECTORY", state_directory), patch("operation_history.LAST_OPERATION_PATH", journal_path):
                save_last_operation("organize", [MoveRecord(source, destination)])
                messages, remaining = undo_last_operation()
            self.assertTrue(destination.is_dir())
            self.assertFalse(source.exists())
            self.assertIsNotNone(remaining)
        self.assertIn("no longer a regular file", messages[0])

    def test_loads_and_clears_legacy_undo_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "clip.mp4"
            destination = root / "destination" / "clip.mp4"
            destination.parent.mkdir()
            destination.write_bytes(b"video")
            new_state = root / "new-state"
            new_journal = new_state / "last-operation.json"
            legacy_journal = root / "old-state" / "last-operation.json"
            legacy_journal.parent.mkdir()
            legacy_journal.write_text(
                '{"operation":"organize","moves":[{"source":"'
                + str(source).replace("\\", "\\\\")
                + '","destination":"'
                + str(destination).replace("\\", "\\\\")
                + '"}]}',
                encoding="utf-8",
            )
            with patch("operation_history.STATE_DIRECTORY", new_state), patch(
                "operation_history.LAST_OPERATION_PATH", new_journal
            ), patch("operation_history.DEFAULT_LAST_OPERATION_PATH", new_journal), patch(
                "operation_history.LEGACY_LAST_OPERATION_PATH", legacy_journal
            ):
                self.assertIsNotNone(load_last_operation())
                _messages, remaining = undo_last_operation()
            self.assertIsNone(remaining)
            self.assertTrue(source.is_file())
            self.assertFalse(legacy_journal.exists())

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

    def test_does_not_flatten_a_source_replaced_by_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "nested" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            plan = build_flatten_plan(root)
            source.unlink()
            source.mkdir()
            messages = flatten_videos(plan, echo=False)
            self.assertTrue(source.is_dir())
            self.assertFalse((root / "clip.mp4").exists())
        self.assertTrue(messages[0].startswith("SKIPPED:"))


class EmptyFolderTests(unittest.TestCase):
    def test_plans_nested_empty_folders_bottom_up_without_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "one" / "two"
            leaf.mkdir(parents=True)
            plan = build_empty_folder_plan(root)
        self.assertEqual(plan, [leaf, leaf.parent])

    def test_keeps_folders_that_contain_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = root / "empty"
            empty.mkdir()
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / ".hidden").touch()
            plan = build_empty_folder_plan(root)
        self.assertEqual(plan, [empty])

    def test_rechecks_emptiness_before_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "empty"
            folder.mkdir()
            plan = build_empty_folder_plan(root)
            (folder / "new-file.txt").touch()
            messages = remove_empty_folders(root, plan)
            self.assertTrue(folder.exists())
        self.assertTrue(messages[0].startswith("SKIPPED:"))

    def test_removes_empty_folders_but_never_the_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "empty"
            child.mkdir()
            messages = remove_empty_folders(root, [child, root])
            self.assertFalse(child.exists())
            self.assertTrue(root.exists())
        self.assertTrue(messages[0].startswith("REMOVED:"))
        self.assertTrue(messages[1].startswith("SKIPPED:"))

    def test_never_removes_a_folder_outside_the_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory)
            outside = Path(other)
            messages = remove_empty_folders(root, [outside])
            self.assertTrue(outside.exists())
        self.assertTrue(messages[0].startswith("SKIPPED:"))


if __name__ == "__main__":
    unittest.main()
