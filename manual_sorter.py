"""Windows 95-style review window for clips with missing game metadata."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from tkinter import messagebox

from media_tools import media_tool_path
from organizer import Clip, classify_clip


BACKGROUND = "#c0c0c0"
WHITE = "#ffffff"
BLACK = "#000000"
MUTED = "#202020"
ACCENT = "#000080"
FONT = ("MS Sans Serif", 10)
FONT_BOLD = ("MS Sans Serif", 10, "bold")
PREVIEW_TIMEOUT_SECONDS = 20


def extract_preview(video: Path, destination: Path) -> str | None:
    """Extract one padded PNG frame, returning a user-readable error on failure."""
    process_options: dict[str, int] = {}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NO_WINDOW
    ffmpeg = media_tool_path("ffmpeg")
    if ffmpeg is None:
        return "FFmpeg is missing. Reinstall Drive Sorter to restore previews."
    try:
        result = subprocess.run(
            [
                str(ffmpeg), "-y", "-ss", "1", "-i", str(video), "-frames:v", "1",
                "-vf", "scale=480:270:force_original_aspect_ratio=decrease,"
                "pad=480:270:(ow-iw)/2:(oh-ih)/2:black", str(destination),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=PREVIEW_TIMEOUT_SECONDS, check=False, **process_options,
        )
    except FileNotFoundError:
        return "FFmpeg is missing. Reinstall Drive Sorter to restore previews."
    except subprocess.TimeoutExpired:
        return "Preview timed out. You can still sort by filename."
    except OSError as error:
        return f"Could not create preview: {error}"
    if result.returncode != 0 or not destination.exists():
        return "No preview frame was available. You can still sort by filename."
    return None


class ManualSortDialog(tk.Toplevel):
    """Classify unknown clips without moving files until the main confirmation."""

    def __init__(
        self, parent: tk.Misc, clips: list[Clip], games: list[str], icon: tk.PhotoImage
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title("Review Unsorted Clips")
        self.geometry("820x585")
        self.minsize(720, 540)
        self.configure(bg=BACKGROUND)
        self.transient(parent)
        self.iconphoto(True, icon)
        self.clips = clips
        self.games = list(games)
        self.filtered_games = list(games)
        self.assignments: dict[Path, Clip] = {}
        self.index = 0
        self.preview_token = 0
        self.preview_image: tk.PhotoImage | None = None
        self.preview_events: Queue[tuple[int, Path, str | None]] = Queue()
        self.preview_running = False
        self.pending_preview: tuple[int, Path, Path] | None = None
        self.temporary_directory = Path(tempfile.mkdtemp(prefix="drive-sorter-preview-"))
        self._dragging = False
        self._closing = False
        self.filter_selection_explicit = False

        self.progress_text = tk.StringVar()
        self.filename_text = tk.StringVar()
        self.year_text = tk.StringVar()
        self.custom_game = tk.StringVar()
        self._build(icon)
        self.protocol("WM_DELETE_WINDOW", self._finish)
        self.bind("<Escape>", lambda _event: self._finish())
        self.bind("<Control-Left>", self._back)
        self.bind("<Control-Right>", self._skip)
        self.bind("<Up>", lambda event: self._dialog_arrow(event, -1))
        self.bind("<Down>", lambda event: self._dialog_arrow(event, 1))
        self.bind("<Return>", self._dialog_enter)
        self._show_clip()
        self.after(75, self._poll_preview)
        self.update_idletasks()
        self.deiconify()
        self.wait_visibility()
        self.lift()
        self.grab_set()
        self._focus_primary_control(force=True)

    def _button(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=BACKGROUND, fg=BLACK,
            activebackground=BACKGROUND, disabledforeground="#606060",
            relief="raised", bd=2, padx=10, pady=4, font=FONT_BOLD,
        )

    def _build(self, icon: tk.PhotoImage) -> None:
        header = tk.Frame(self, bg=ACCENT, padx=6, pady=4, relief="raised", bd=2)
        header.pack(fill="x")
        self.header_icon = icon.subsample(32, 32)
        tk.Label(header, image=self.header_icon, bg=ACCENT).pack(side="left", padx=(0, 6))
        tk.Label(
            header, text="Manual Clip Sorter", bg=ACCENT, fg=WHITE,
            font=("MS Sans Serif", 10, "bold"),
        ).pack(side="left")
        tk.Label(
            header, textvariable=self.progress_text, bg=ACCENT, fg=WHITE, font=FONT,
        ).pack(side="right", padx=5)

        body = tk.Frame(self, bg=BACKGROUND, padx=12, pady=10)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=BACKGROUND)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(
            left, text="CLIP PREVIEW", bg=BACKGROUND, fg=BLACK,
            font=("MS Sans Serif", 9, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self.preview = tk.Label(
            left, text="Loading preview...", bg=BLACK, fg=WHITE, width=60, height=17,
            relief="sunken", bd=2, font=FONT, cursor="hand2",
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<ButtonPress-1>", self._start_drag)
        self.preview.bind("<B1-Motion>", self._drag_over_games)
        self.preview.bind("<ButtonRelease-1>", self._drop_on_game)
        tk.Label(
            left, textvariable=self.filename_text, bg=BACKGROUND, fg=BLACK,
            anchor="w", justify="left", wraplength=475, font=("MS Sans Serif", 9, "bold"),
        ).pack(fill="x", pady=(7, 1))
        tk.Label(left, textvariable=self.year_text, bg=BACKGROUND, fg=MUTED, anchor="w", font=FONT).pack(fill="x")
        tk.Label(
            left, text="Keyboard: Up/Down then Enter. Start typing to filter games.",
            bg=BACKGROUND, fg=MUTED, anchor="w", font=("MS Sans Serif", 8, "bold"),
        ).pack(fill="x", pady=(5, 0))

        right = tk.Frame(body, bg=BACKGROUND, width=280, padx=10)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(
            right, text="GAME FOLDERS", bg=BACKGROUND, fg=BLACK,
            font=("MS Sans Serif", 9, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 4))
        list_frame = tk.Frame(right, bg=WHITE, relief="sunken", bd=2)
        list_frame.pack(fill="both", expand=True)
        self.game_list = tk.Listbox(
            list_frame, bg=WHITE, fg=BLACK, selectbackground=ACCENT, selectforeground=WHITE,
            relief="flat", bd=0, exportselection=False, font=FONT,
        )
        scrollbar = tk.Scrollbar(list_frame, command=self.game_list.yview)
        self.game_list.configure(yscrollcommand=scrollbar.set)
        self.game_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._fill_game_list(self.filtered_games)
        self.game_list.bind("<Double-Button-1>", lambda _event: self._assign_selected())
        self.game_list.bind("<Return>", self._assign_selected)
        self.game_list.bind("<KeyPress>", self._start_typing, add="+")

        self.assign_button = self._button(right, "Assign to selected game", self._assign_selected)
        self.assign_button.pack(fill="x", pady=(7, 10))
        tk.Label(right, text="TYPE OR FILTER GAME", bg=BACKGROUND, fg=BLACK, font=("MS Sans Serif", 9, "bold"), anchor="w").pack(fill="x")
        self.game_entry = tk.Entry(
            right, textvariable=self.custom_game, bg=WHITE, fg=BLACK,
            relief="sunken", bd=2, font=FONT,
        )
        self.game_entry.pack(fill="x", ipady=3, pady=(4, 5))
        self.game_entry.bind("<Return>", self._assign_from_entry)
        self.game_entry.bind("<Up>", lambda _event: self._move_game_selection(-1, explicit=True))
        self.game_entry.bind("<Down>", lambda _event: self._move_game_selection(1, explicit=True))
        self.custom_game.trace_add("write", self._filter_games)
        self._button(right, "Assign typed game", self._assign_from_entry).pack(fill="x")
        tk.Label(
            right,
            text="New folders are created after review when you click Organize.",
            bg=BACKGROUND,
            fg=MUTED,
            justify="left",
            anchor="w",
            wraplength=250,
            font=("MS Sans Serif", 8, "bold"),
        ).pack(fill="x", pady=(6, 0))

        footer = tk.Frame(self, bg=BACKGROUND, padx=12, pady=9, relief="raised", bd=1)
        footer.pack(fill="x")
        self._button(footer, "Done", self._finish).pack(side="right")
        self.skip_button = self._button(footer, "Skip", self._skip)
        self.skip_button.pack(side="right", padx=(0, 7))
        self.back_button = self._button(footer, "< Back", self._back)
        self.back_button.pack(side="left")

    def _show_clip(self) -> None:
        if self.index >= len(self.clips):
            self._finish()
            return
        clip = self.clips[self.index]
        self.progress_text.set(f"Clip {self.index + 1} of {len(self.clips)}")
        self.filename_text.set(clip.path.name)
        self.year_text.set(f"Destination year: {clip.year if clip.year else 'Unknown Year'}")
        self.back_button.configure(state="normal" if self.index else "disabled")
        assigned = self.assignments.get(clip.path)
        if assigned and assigned.game in self.filtered_games:
            self._select_game(assigned.game)
        self.preview.configure(image="", text="Loading preview...", cursor="watch")
        self.preview_image = None
        self.preview_token += 1
        token = self.preview_token
        destination = self.temporary_directory / f"preview-{token}.png"

        self._request_preview(token, clip.path, destination)
        self.after_idle(self._focus_primary_control)

    def _request_preview(self, token: int, video: Path, destination: Path) -> None:
        """Keep at most one FFmpeg process active and only one pending preview."""
        self.pending_preview = (token, video, destination)
        if not self.preview_running:
            self._start_pending_preview()

    def _start_pending_preview(self) -> None:
        if self._closing or self.pending_preview is None:
            return
        token, video, destination = self.pending_preview
        self.pending_preview = None
        self.preview_running = True

        def worker() -> None:
            self.preview_events.put((token, destination, extract_preview(video, destination)))

        threading.Thread(target=worker, daemon=True).start()

    def _focus_primary_control(self, force: bool = False) -> None:
        if self.game_list.size():
            target = self.game_list
        else:
            target = self.game_entry
        if force:
            target.focus_force()
        else:
            target.focus_set()

    def _dialog_arrow(self, _event: object, direction: int) -> str | None:
        # Listbox and entry bindings already handle arrows when they own focus.
        if self.focus_get() in (self.game_list, self.game_entry):
            return None
        return self._move_game_selection(direction)

    def _dialog_enter(self, _event: object = None) -> str | None:
        # Their more specific bindings decide between a selected or typed game.
        if self.focus_get() in (self.game_list, self.game_entry):
            return None
        return self._assign_selected()

    def _start_typing(self, event: tk.Event[tk.Listbox]) -> str | None:
        if event.keysym == "Return":
            return "break"
        if event.char and event.char.isprintable() and not (event.state & 0xC):
            self.custom_game.set(self.custom_game.get() + event.char)
            self.game_entry.focus_set()
            self.game_entry.icursor("end")
            return "break"
        return None

    def _fill_game_list(self, games: list[str]) -> None:
        self.game_list.delete(0, "end")
        for game in games:
            self.game_list.insert("end", game)
        if games:
            self.game_list.selection_set(0)
            self.game_list.activate(0)

    def _select_game(self, game: str) -> None:
        """Synchronize the visible selection and Tkinter's keyboard-active row."""
        if game not in self.filtered_games:
            return
        index = self.filtered_games.index(game)
        self.game_list.selection_clear(0, "end")
        self.game_list.selection_set(index)
        self.game_list.activate(index)
        self.game_list.see(index)

    def _filter_games(self, *_args: object) -> None:
        self.filter_selection_explicit = False
        query = self.custom_game.get().strip().casefold()
        if query:
            matches = [game for game in self.games if query in game.casefold()]
            matches.sort(key=lambda game: (not game.casefold().startswith(query), game.casefold()))
            self.filtered_games = matches
        else:
            self.filtered_games = list(self.games)
        self._fill_game_list(self.filtered_games)

    def _move_game_selection(self, direction: int, explicit: bool = False) -> str:
        size = self.game_list.size()
        if not size:
            return "break"
        if explicit:
            self.filter_selection_explicit = True
        selection = self.game_list.curselection()
        current = selection[0] if selection else (-1 if direction > 0 else size)
        target = min(max(current + direction, 0), size - 1)
        self.game_list.selection_clear(0, "end")
        self.game_list.selection_set(target)
        self.game_list.activate(target)
        self.game_list.see(target)
        return "break"

    def _poll_preview(self) -> None:
        try:
            while True:
                token, destination, error = self.preview_events.get_nowait()
                self.preview_running = False
                if token != self.preview_token:
                    continue
                if error:
                    self.preview.configure(image="", text=error, cursor="hand2")
                else:
                    try:
                        self.preview_image = tk.PhotoImage(file=destination)
                    except tk.TclError:
                        self.preview.configure(image="", text="Preview could not be displayed.", cursor="hand2")
                    else:
                        self.preview.configure(image=self.preview_image, text="", cursor="hand2")
        except Empty:
            pass
        self._start_pending_preview()
        if self.winfo_exists():
            self.after(75, self._poll_preview)

    def _selected_game(self) -> str | None:
        selection = self.game_list.curselection()
        return self.game_list.get(selection[0]) if selection else None

    def _assign(self, game: str) -> None:
        try:
            classified = classify_clip(self.clips[self.index], game)
        except ValueError as error:
            messagebox.showerror("Drive Sorter", str(error), parent=self)
            return
        self.assignments[classified.path] = classified
        if classified.game not in self.games:
            self.games.append(classified.game)
            self.games.sort(key=str.casefold)
        self.custom_game.set("")
        self._select_game(classified.game)
        self.index += 1
        self._show_clip()

    def _assign_selected(self, _event: object = None) -> str:
        game = self._selected_game()
        if game is None:
            messagebox.showinfo("Drive Sorter", "Select a game folder first.", parent=self)
            return "break"
        self._assign(game)
        return "break"

    def _assign_custom(self) -> None:
        self._assign(self.custom_game.get())

    def _assign_from_entry(self, _event: object = None) -> str:
        typed_game = self.custom_game.get().strip()
        selected_game = self._selected_game()
        exact_game = next(
            (game for game in self.games if game.casefold() == typed_game.casefold()),
            None,
        ) if typed_game else None
        if typed_game:
            if self.filter_selection_explicit and selected_game:
                self._assign(selected_game)
            else:
                self._assign(exact_game or typed_game)
        elif selected_game:
            self._assign(selected_game)
        else:
            messagebox.showinfo("Drive Sorter", "Type or select a game first.", parent=self)
        return "break"

    def _skip(self, _event: object = None) -> str:
        self.assignments.pop(self.clips[self.index].path, None)
        self.index += 1
        self._show_clip()
        return "break"

    def _back(self, _event: object = None) -> str:
        if self.index:
            self.index -= 1
            self._show_clip()
        return "break"

    def _start_drag(self, _event: tk.Event[tk.Misc]) -> None:
        self._dragging = True
        self.preview.configure(cursor="fleur", relief="raised")

    def _drag_over_games(self, event: tk.Event[tk.Misc]) -> None:
        x = event.x_root - self.game_list.winfo_rootx()
        y = event.y_root - self.game_list.winfo_rooty()
        if 0 <= x < self.game_list.winfo_width() and 0 <= y < self.game_list.winfo_height():
            nearest = self.game_list.nearest(y)
            self.game_list.selection_clear(0, "end")
            self.game_list.selection_set(nearest)
            self.game_list.activate(nearest)

    def _drop_on_game(self, event: tk.Event[tk.Misc]) -> None:
        self.preview.configure(cursor="hand2", relief="sunken")
        if not self._dragging:
            return
        self._dragging = False
        x = event.x_root - self.game_list.winfo_rootx()
        y = event.y_root - self.game_list.winfo_rooty()
        if 0 <= x < self.game_list.winfo_width() and 0 <= y < self.game_list.winfo_height():
            self._assign_selected()

    def _finish(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.pending_preview = None
        # A closing FFmpeg process can briefly retain its output file on Windows.
        shutil.rmtree(self.temporary_directory, ignore_errors=True)
        self.destroy()


def review_unsorted(
    parent: tk.Misc, clips: list[Clip], games: list[str], icon: tk.PhotoImage
) -> dict[Path, Clip]:
    """Open the modal sorter and return only clips the user classified."""
    dialog = ManualSortDialog(parent, clips, games, icon)
    parent.wait_window(dialog)
    return dialog.assignments
