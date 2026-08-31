"""A small desktop interface for Drive Sorter."""

from __future__ import annotations

import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from queue import Empty, Queue
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk

from dev_flatten_videos import build_flatten_plan, flatten_videos
from organizer import Clip, ScanCancelled, PlannedMove, build_plan, file_scanner, organize_clips
from operation_history import MoveRecord, load_last_operation, save_last_operation, undo_last_operation


BACKGROUND = "#c0c0c0"
PANEL = "#ffffff"
TEXT = "#000000"
BLACK = "#000000"
MUTED = "#404040"
ACCENT = "#000080"
WARNING = "#804000"
ERROR = "#800000"
FONT = ("MS Sans Serif", 10)


class DriveSorterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Drive Sorter")
        self.geometry("940x640")
        self.minsize(700, 460)
        self.configure(bg=BACKGROUND)

        icon_path = Path(__file__).resolve().parent / "assets" / "drive-sorter-icon.png"
        self.app_icon = tk.PhotoImage(file=icon_path)
        self.header_icon = self.app_icon.subsample(32, 32)
        self.iconphoto(True, self.app_icon)

        default_directory = Path(__file__).resolve().parent / "test-videos"
        self.directory = tk.StringVar(value=str(default_directory))
        self.status = tk.StringVar(value="Choose a folder, then scan it.")
        self.signal = tk.StringVar(value="[ READY TO SCAN ]")
        self.progress_value = tk.DoubleVar(value=0)
        self.show_details = tk.BooleanVar(value=False)
        self.rename_duplicates = tk.BooleanVar(value=False)
        self.plan: list[PlannedMove] = []
        self.scanned_clips: list[Clip] = []
        self.flatten_plan: list[tuple[Path, Path]] = []
        self.scanned_folder: Path | None = None
        self.events: Queue[tuple[str, object]] = Queue()
        self.cancel_requested = threading.Event()
        self.active_operation: str | None = None
        self.animation_queue: list[tuple[Path, int]] = []
        self.animation_job: str | None = None
        self.animated_destinations: set[Path] = set()
        self.card_title_font = tkfont.Font(family="MS Sans Serif", size=9, weight="bold")
        self.card_font = tkfont.Font(family="MS Sans Serif", size=9)
        self.card_status_font = tkfont.Font(family="MS Sans Serif", size=8, weight="bold")

        style = ttk.Style(self)
        style.theme_use("classic")
        style.configure(
            "DriveSorter.Horizontal.TProgressbar",
            troughcolor="#ffffff", background=ACCENT, bordercolor="#808080", lightcolor=ACCENT,
            darkcolor=ACCENT, thickness=16,
        )
        self._build_interface()
        self._refresh_undo_button()

    def _build_interface(self) -> None:
        header = tk.Frame(self, bg=ACCENT, padx=6, pady=4, relief="raised", bd=2)
        header.pack(fill="x")
        tk.Label(header, image=self.header_icon, bg=ACCENT).pack(side="left", padx=(0, 6))
        title_area = tk.Frame(header, bg=ACCENT)
        title_area.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_area, text="Drive Sorter", bg=ACCENT, fg="#ffffff",
            font=("MS Sans Serif", 11, "bold"),
        ).pack(anchor="w")
        self.tools_button = tk.Button(
            header, text="<", command=self._toggle_tools_panel, bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT, activeforeground="#ffffff", disabledforeground="#b0b0b0",
            relief="flat", bd=1, padx=5, pady=0, font=("MS Sans Serif", 9, "bold"),
        )
        self.tools_button.pack(side="right")

        controls = tk.Frame(self, bg=BACKGROUND, padx=12, pady=10)
        controls.pack(fill="x")
        row = tk.Frame(controls, bg=BACKGROUND)
        row.pack(fill="x")
        tk.Label(row, text="Folder:", bg=BACKGROUND, fg=TEXT, font=FONT).pack(side="left", padx=(0, 6))
        self.folder_entry = tk.Entry(
            row, textvariable=self.directory, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="sunken", bd=2, highlightthickness=0, font=FONT,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.browse_button = self._button(row, "Browse", self.choose_folder)
        self.browse_button.pack(side="left", padx=(8, 0))
        actions = tk.Frame(controls, bg=BACKGROUND)
        actions.pack(anchor="w", pady=(8, 0))
        self.scan_button = self._button(actions, "Scan", self.scan)
        self.scan_button.pack(side="left")
        self.organize_button = self._button(actions, "Organize", self.organize)
        self.organize_button.pack(side="left", padx=(8, 0))
        self.organize_button.configure(state="disabled")
        self.progress = ttk.Progressbar(
            controls, mode="determinate", maximum=1, variable=self.progress_value,
            style="DriveSorter.Horizontal.TProgressbar",
        )
        self.move_animation = tk.Canvas(
            controls, height=48, bg="#ffffff", relief="sunken", bd=2,
            highlightthickness=0,
        )
        self._draw_animation_idle("Waiting for a move plan")
        self.signal_label = tk.Label(
            controls, textvariable=self.signal, bg=BACKGROUND, fg=ACCENT,
            font=("MS Sans Serif", 10, "bold"),
        )
        self.signal_label.pack(anchor="w", pady=(8, 0))
        output_frame = tk.Frame(self, bg=BACKGROUND, padx=12, pady=6)
        output_frame.pack(fill="both", expand=True)
        tk.Label(output_frame, text="Scan result", bg=BACKGROUND, fg=TEXT, font=("MS Sans Serif", 10, "bold")).pack(anchor="w", pady=(0, 4))
        workspace = tk.Frame(output_frame, bg=BACKGROUND)
        workspace.pack(fill="both", expand=True)
        text_frame = tk.Frame(workspace, bg=PANEL)
        text_frame.pack(side="left", fill="both", expand=True)
        self.tools_panel = tk.Frame(self, bg=BACKGROUND, width=190, relief="raised", bd=2)
        tools_content = tk.Frame(self.tools_panel, bg=BACKGROUND, padx=8, pady=6)
        tools_content.pack(fill="x")
        self.flatten_button = self._sidebar_action(tools_content, "Flatten all", self.flatten)
        self.flatten_button.pack(fill="x")
        self._sidebar_divider(tools_content).pack(fill="x")
        self.undo_button = self._sidebar_action(tools_content, "Undo last", self.undo_last)
        self.undo_button.pack(fill="x")
        self._sidebar_divider(tools_content).pack(fill="x")
        self.rename_toggle = tk.Checkbutton(
            tools_content, text="Auto-rename duplicate clip names", variable=self.rename_duplicates,
            command=self._toggle_duplicate_renaming, bg=BACKGROUND, fg=MUTED, selectcolor=BACKGROUND,
            activebackground=BACKGROUND, activeforeground=TEXT, font=FONT, anchor="w", justify="left",
            wraplength=175, highlightthickness=0, padx=0, pady=8,
        )
        self.rename_toggle.pack(fill="x")
        self.cancel_divider = self._sidebar_divider(tools_content)
        self.cancel_button = self._sidebar_action(tools_content, "Cancel scan", self.cancel_scan)
        self.cancel_button.configure(state="disabled")
        self.destination_cards: list[tuple[Path, int, str]] = []
        self.destination_progress: dict[Path, int] = {}
        self.show_destination_progress = False
        self.destination_frame = tk.Frame(text_frame, bg=PANEL)
        self.destination_heading = tk.Label(
            self.destination_frame, text="Folders receiving clips", bg=PANEL, fg=MUTED,
            font=("MS Sans Serif", 9, "bold"), anchor="w",
        )
        self.destination_heading.pack(fill="x", padx=8, pady=(7, 2))
        cards_area = tk.Frame(self.destination_frame, bg=PANEL)
        cards_area.pack(fill="both", expand=True, padx=8, pady=(0, 7))
        self.destination_canvas = tk.Canvas(
            cards_area, height=118, bg=PANEL, relief="flat", highlightthickness=0,
        )
        self.destination_scrollbar = tk.Scrollbar(
            cards_area, command=self.destination_canvas.yview, relief="flat",
        )
        self.destination_canvas.configure(yscrollcommand=self.destination_scrollbar.set)
        self.destination_canvas.pack(side="left", fill="both", expand=True)
        self.destination_scrollbar.pack(side="right", fill="y")
        self.destination_canvas.bind("<Configure>", self._redraw_destination_cards)
        self.bind_all("<MouseWheel>", self._scroll_destination_cards, add="+")
        self.details_frame = tk.Frame(text_frame, bg=PANEL)
        self.output = tk.Text(
            self.details_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
            padx=8, pady=8, wrap="word", font=FONT, state="disabled",
        )
        scrollbar = tk.Scrollbar(self.details_frame, command=self.output.yview, relief="flat")
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for tag, color in (("ready", ACCENT), ("warning", WARNING), ("error", ERROR), ("muted", MUTED)):
            self.output.tag_configure(tag, foreground=color)
        self.details_toggle = self._button(text_frame, "+ Details", self._toggle_details)
        self.details_toggle.pack(side="bottom", anchor="w", padx=8, pady=7)

        footer = tk.Label(self, textvariable=self.status, bg=BACKGROUND, fg=MUTED, font=FONT, anchor="w", padx=12, pady=5)
        footer.pack(fill="x")

    def _button(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=BACKGROUND, fg=TEXT,
            activebackground=BACKGROUND, activeforeground=TEXT, disabledforeground="#808080",
            relief="raised", bd=2, padx=10, pady=4, font=FONT,
        )

    def _small_button(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=BACKGROUND, fg=MUTED,
            activebackground=BACKGROUND, activeforeground=TEXT, disabledforeground="#808080",
            relief="raised", bd=2, padx=6, pady=1, font=("MS Sans Serif", 8),
        )

    def _sidebar_action(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        def choose() -> None:
            self._hide_tools_panel()
            command()

        return tk.Button(
            parent, text=text, command=choose, bg=BACKGROUND, fg=TEXT,
            activebackground="#a0a0a0", activeforeground=TEXT, disabledforeground="#808080",
            relief="flat", bd=0, highlightthickness=0, anchor="w", padx=8, pady=8, font=FONT,
        )

    @staticmethod
    def _sidebar_divider(parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, bg="#808080", height=1)

    def _toggle_tools_panel(self) -> None:
        if self.tools_panel.winfo_manager():
            self._hide_tools_panel()
        else:
            self._show_tools_panel()

    def _show_tools_panel(self) -> None:
        self.tools_panel.place(relx=1.0, x=-8, y=38, anchor="ne", width=190)
        self.tools_panel.lift()

    def _hide_tools_panel(self) -> None:
        self.tools_panel.place_forget()

    def _toggle_duplicate_renaming(self) -> None:
        self.refresh_plan()
        self._hide_tools_panel()

    def _show_progress(self) -> None:
        if not self.progress.winfo_manager():
            self.progress.pack(fill="x", pady=(10, 0), before=self.signal_label)

    def _hide_progress(self) -> None:
        self.progress.pack_forget()

    def _confirm(self, title: str, message: str, action: str) -> bool:
        """Show a Drive Sorter-styled modal confirmation over this window."""
        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title(title)
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.minsize(520, 0)
        dialog.transient(self)
        dialog.iconphoto(True, self.app_icon)
        result = False

        header = tk.Frame(dialog, bg=ACCENT, padx=6, pady=4, relief="raised", bd=2)
        header.pack(fill="x")
        tk.Label(header, image=self.header_icon, bg=ACCENT).pack(side="left", padx=(0, 6))
        tk.Label(header, text="Drive Sorter", bg=ACCENT, fg="#ffffff", font=("MS Sans Serif", 9, "bold")).pack(side="left")

        body = tk.Frame(dialog, bg=BACKGROUND, padx=16, pady=16)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=message, bg=BACKGROUND, fg=TEXT, justify="left", anchor="w", wraplength=460, font=FONT).pack(fill="x")
        tk.Frame(body, bg="#808080", height=2).pack(fill="x", pady=(16, 10))
        buttons = tk.Frame(body, bg=BACKGROUND)
        buttons.pack(anchor="e")

        def close(confirmed: bool) -> None:
            nonlocal result
            result = confirmed
            dialog.destroy()

        cancel = self._button(buttons, "Cancel", lambda: close(False))
        cancel.pack(side="right")
        confirm = self._button(buttons, action, lambda: close(True))
        confirm.pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
        dialog.bind("<Escape>", lambda _event: close(False))
        dialog.bind("<Return>", lambda _event: close(True))

        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dialog.deiconify()
        dialog.grab_set()
        confirm.focus_set()
        self.wait_window(dialog)
        return result

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(parent=self, initialdir=self.directory.get() or None)
        if chosen:
            self.directory.set(chosen)

    def write(self, text: str, tag: str | None = None) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text, tag)
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear_output(self) -> None:
        self._set_destination_cards([])
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _set_destination_cards(self, cards: list[tuple[Path, int, str]]) -> None:
        self.destination_cards = cards
        if not cards:
            self.destination_progress = {}
            self.show_destination_progress = False
        if cards:
            fill = "x" if self.show_details.get() else "both"
            expand = not self.show_details.get()
            if self.details_frame.winfo_manager():
                self.destination_frame.pack(fill=fill, expand=expand, side="top", before=self.details_frame)
            else:
                self.destination_frame.pack(fill=fill, expand=expand, side="top")
        else:
            self.destination_frame.pack_forget()
        self._draw_destination_cards()

    def _redraw_destination_cards(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self._draw_destination_cards()

    def _scroll_destination_cards(self, event: tk.Event[tk.Misc]) -> str | None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget in (self.destination_canvas, self.destination_scrollbar):
                units = max(1, abs(event.delta) // 120)
                direction = -1 if event.delta > 0 else 1
                self.destination_canvas.yview_scroll(direction * units, "units")
                return "break"
            widget = widget.master
        return None

    def _draw_destination_cards(self) -> None:
        canvas = self.destination_canvas
        canvas.delete("all")
        if not self.destination_cards:
            canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        groups: dict[str, list[tuple[Path, int, str, str]]] = {}
        for destination, count, state in self.destination_cards:
            if destination.name == "Unsorted":
                game, year = "Unsorted", "Needs review"
            else:
                game, year = destination.parent.name, destination.name
            groups.setdefault(game, []).append((destination, count, state, year))

        card_width = 280
        gap = 6
        available_width = max(canvas.winfo_width(), card_width)
        columns = max(1, (available_width + gap) // (card_width + gap))
        grouped_cards = sorted(groups.items(), key=lambda item: item[0].lower())
        row_heights = [
            max(72, 42 + max(len(items) for _game, items in grouped_cards[row:row + columns]) * 26)
            for row in range(0, len(grouped_cards), columns)
        ]
        row_tops: list[int] = []
        current_top = 0
        for row_height in row_heights:
            row_tops.append(current_top)
            current_top += row_height + gap

        for index, (game, items) in enumerate(grouped_cards):
            column = index % columns
            row = index // columns
            left = column * (card_width + gap)
            top = row_tops[row]
            right = left + card_width
            bottom = top + row_heights[row]
            canvas.create_rectangle(left + 1, top + 1, right, bottom, fill="#808080", outline="")
            canvas.create_rectangle(left, top, right - 1, bottom - 1, fill=BACKGROUND, outline="#ffffff")
            canvas.create_rectangle(left + 2, top + 2, right - 3, bottom - 3, outline="#000000")
            canvas.create_polygon(
                left + 10, top + 12, left + 28, top + 12, left + 34, top + 18,
                left + 55, top + 18, left + 55, top + 34, left + 10, top + 34,
                fill="#ffff00", outline=BLACK,
            )
            canvas.create_text(
                left + 63, top + 23, anchor="w",
                text=self._fit_card_text(game, right - (left + 63) - 8, self.card_title_font),
                fill=TEXT, font=self.card_title_font,
            )
            canvas.create_line(left + 8, top + 40, right - 8, top + 40, fill="#808080")
            for item_index, (destination, count, state, year) in enumerate(items):
                item_top = top + 44 + item_index * 26
                canvas.create_polygon(
                    left + 12, item_top + 5, left + 22, item_top + 5, left + 26, item_top + 9,
                    left + 39, item_top + 9, left + 39, item_top + 20, left + 12, item_top + 20,
                    fill="#ffff00", outline=BLACK,
                )
                year_width = 110
                canvas.create_text(
                    left + 47, item_top + 13, anchor="w",
                    text=self._fit_card_text(year, year_width, self.card_font),
                    fill=MUTED, font=self.card_font,
                )
                if self.show_destination_progress:
                    completed = self.destination_progress.get(destination, 0)
                    count_label = f"{completed}/{count}"
                else:
                    count_label = f"{count} clip{'s' if count != 1 else ''}"
                canvas.create_text(right - 62, item_top + 13, anchor="e", text=count_label, fill=ACCENT, font=self.card_font)
                canvas.create_text(right - 8, item_top + 13, anchor="e", text=state, fill=ACCENT if state == "CREATE" else MUTED, font=self.card_status_font)

        canvas.configure(scrollregion=(0, 0, available_width, max(current_top - gap, 0)))

    @staticmethod
    def _fit_card_text(text: str, max_width: int, font: tkfont.Font) -> str:
        if font.measure(text) <= max_width:
            return text
        shortened = ""
        for character in text:
            if font.measure(shortened + character + "...") > max_width:
                break
            shortened += character
        return shortened + "..."

    def _toggle_details(self) -> None:
        showing_details = not self.show_details.get()
        self.show_details.set(showing_details)
        if showing_details:
            self.details_frame.pack(fill="both", expand=True)
            self.details_toggle.configure(text="- Hide details")
        else:
            self.details_frame.pack_forget()
            self.details_toggle.configure(text="+ Details")
        self.refresh_plan()

    def _set_signal(self, text: str, color: str) -> None:
        self.signal.set(text)
        self.signal_label.configure(fg=color)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.folder_entry.configure(state=state)
        self.browse_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.details_toggle.configure(state=state)
        tools_state = "normal" if busy and self.active_operation == "scan" else state
        self.tools_button.configure(state=tools_state)
        self.flatten_button.configure(state=state)
        self.undo_button.configure(state="disabled" if busy or not load_last_operation() else "normal")
        self.rename_toggle.configure(state=state)
        if busy and self.active_operation == "scan":
            if not self.cancel_button.winfo_manager():
                self.cancel_divider.pack(fill="x")
                self.cancel_button.pack(fill="x")
            self.cancel_button.configure(state="normal")
        else:
            self.cancel_divider.pack_forget()
            self.cancel_button.pack_forget()
        if busy:
            self.organize_button.configure(state="disabled")
        else:
            self._hide_progress()
            self.active_operation = None

    def _refresh_undo_button(self) -> None:
        self.undo_button.configure(state="normal" if load_last_operation() else "disabled")

    def _draw_animation_idle(self, message: str) -> None:
        self.move_animation.delete("all")
        self.move_animation.create_text(
            8, 23, anchor="w", text=message, fill=MUTED, font=FONT
        )

    def _show_animation(self) -> None:
        if not self.move_animation.winfo_manager():
            self.move_animation.pack(fill="x", pady=(8, 0), before=self.signal_label)

    def _hide_animation(self) -> None:
        self.move_animation.pack_forget()

    def _reset_animation(self, message: str) -> None:
        self.animation_queue.clear()
        self.animated_destinations.clear()
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        self._draw_animation_idle(message)

    def _queue_destination_animation(self, destination: Path, clip_count: int) -> None:
        self.animation_queue.append((destination, clip_count))
        self._show_animation()
        if self.animation_job is None:
            self._play_next_animation()

    def _play_next_animation(self) -> None:
        if not self.animation_queue:
            self.animation_job = None
            self._draw_animation_idle("All destination folders updated")
            self.after(350, self._hide_animation)
            return
        self.animation_destination, self.animation_clip_count = self.animation_queue.pop(0)
        self.animation_step = 0
        self._animate_bundle_to_folder()

    def _animate_bundle_to_folder(self) -> None:
        canvas = self.move_animation
        canvas.delete("all")
        width = max(canvas.winfo_width(), 700)
        folder_left = width - 115
        start_left = 16
        target_left = folder_left - 54
        progress = min(self.animation_step / 12, 1)
        clip_left = start_left + (target_left - start_left) * progress
        if self.animation_destination.name == "Unsorted":
            folder_name = "Unsorted / Needs review"
        else:
            folder_name = f"{self.animation_destination.parent.name} / {self.animation_destination.name}"

        canvas.create_text(
            8, 8, anchor="nw", text=f"Sending {self.animation_clip_count} clip(s)",
            fill=MUTED, font=("MS Sans Serif", 8),
        )
        for offset in (8, 4, 0):
            canvas.create_rectangle(clip_left + offset, 20 - offset // 2, clip_left + 48 + offset, 39 - offset // 2, fill="#000080", outline=BLACK)
        canvas.create_rectangle(clip_left + 5, 24, clip_left + 25, 27, fill="#ffffff", outline="")
        canvas.create_text(clip_left + 36, 29, text="MP4", fill="#ffffff", font=("MS Sans Serif", 7, "bold"))
        canvas.create_polygon(
            folder_left, 18, folder_left + 27, 18, folder_left + 34, 24,
            folder_left + 78, 24, folder_left + 78, 40, folder_left, 40,
            fill="#ffff00", outline=BLACK,
        )
        canvas.create_text(folder_left + 39, 45, text=folder_name[:28], anchor="s", fill=TEXT, font=("MS Sans Serif", 7))

        if self.animation_step < 12:
            self.animation_step += 1
            self.animation_job = self.after(16, self._animate_bundle_to_folder)
        else:
            self.animation_job = self.after(90, self._play_next_animation)

    def scan(self) -> None:
        folder = Path(self.directory.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror("Drive Sorter", f"This is not a folder:\n{folder}", parent=self)
            return
        self.plan = []
        self.scanned_clips = []
        self.scanned_folder = folder
        self.events = Queue()
        self.cancel_requested.clear()
        self.active_operation = "scan"
        self._show_progress()
        self.progress.configure(maximum=1)
        self.progress_value.set(0)
        self.clear_output()
        self._reset_animation("Scanning videos...")
        self.write("SCANNING...\n", "muted")
        self._set_signal("[ SCANNING ]", MUTED)
        self.status.set("Reading video metadata...")
        self._set_busy(True)
        threading.Thread(target=self._scan_worker, args=(folder,), daemon=True).start()
        self.after(75, self._poll_events)

    def _scan_worker(self, folder: Path) -> None:
        try:
            output = folder / "Organized"
            clips = file_scanner(folder, output, self._report_scan_progress, cancelled=self.cancel_requested.is_set)
            self.events.put(("complete", clips))
        except ScanCancelled:
            self.events.put(("scan_cancelled", None))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _report_scan_progress(self, completed: int, total: int, file: Path) -> None:
        self.events.put(("scan_progress", (completed, total, file)))

    def _poll_events(self) -> None:
        finished = False
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "scan_progress":
                    completed, total, file = payload
                    self.progress.configure(maximum=max(total, 1))
                    self.progress_value.set(completed)
                    self.status.set(f"Reading metadata: {completed}/{total} - {file.name}")
                elif event == "move_progress":
                    completed, total, move, message = payload
                    self.progress.configure(maximum=max(total, 1))
                    self.progress_value.set(completed)
                    self.status.set(f"Moving: {completed}/{total} - {move.clip.path.name}")
                    if message.startswith("MOVED"):
                        destination = move.destination.parent
                        self.destination_progress[destination] = self.destination_progress.get(destination, 0) + 1
                        self._draw_destination_cards()
                        if destination not in self.animated_destinations:
                            planned_count = next(
                                count for folder, count, _state in self.destination_cards if folder == destination
                            )
                            self.animated_destinations.add(destination)
                            self._queue_destination_animation(destination, planned_count)
                elif event == "complete":
                    self._show_plan(payload)
                    finished = True
                elif event == "move_complete":
                    self._show_move_result(payload)
                    finished = True
                elif event == "scan_cancelled":
                    self._show_scan_cancelled()
                    finished = True
                elif event == "flatten_plan":
                    self._show_flatten_plan(payload)
                    finished = True
                elif event == "flatten_progress":
                    completed, total, source, _destination, _message = payload
                    self.progress.configure(maximum=max(total, 1))
                    self.progress_value.set(completed)
                    self.status.set(f"Flattening: {completed}/{total} - {source.name}")
                elif event == "flatten_complete":
                    self._show_flatten_result(payload)
                    finished = True
                elif event == "undo_complete":
                    self._show_undo_result(payload)
                    finished = True
                elif event == "failed":
                    self._show_failure(str(payload))
                    finished = True
        except Empty:
            pass
        if not finished:
            self.after(75, self._poll_events)

    def _show_failure(self, error: str) -> None:
        self.write(f"FAILED: {error}\n", "error")
        self._set_signal("[ OPERATION FAILED ]", ERROR)
        self.status.set("Operation failed. Nothing else was attempted.")
        self._set_busy(False)
        self.organize_button.configure(state="disabled")

    def cancel_scan(self) -> None:
        if self.active_operation != "scan":
            return
        self.cancel_requested.set()
        self.cancel_button.configure(state="disabled")
        self._set_signal("[ CANCELLING SCAN ]", WARNING)
        self.status.set("Finishing active metadata reads, then cancelling...")

    def _show_scan_cancelled(self) -> None:
        self.plan = []
        self.clear_output()
        self._reset_animation("Scan cancelled")
        self._set_signal("[ SCAN CANCELLED ]", WARNING)
        self.status.set("Scan cancelled. No files were moved.")
        self._set_busy(False)
        self.organize_button.configure(state="disabled")

    def refresh_plan(self) -> None:
        if self.scanned_clips:
            self._show_plan(self.scanned_clips)

    def _show_plan(self, clips: list[Clip]) -> None:
        self.scanned_clips = clips
        output = (self.scanned_folder or Path(self.directory.get()).expanduser()) / "Organized"
        plan = build_plan(clips, output, rename_duplicates=self.rename_duplicates.get())
        self.plan = plan
        self.show_destination_progress = False
        self.destination_progress = {}
        self.clear_output()
        ready = sum(move.status == "READY" for move in plan)
        conflicts = [move for move in plan if move.status != "READY"]
        destinations = Counter(move.destination.parent for move in plan if move.status == "READY")
        unsorted = sum(move.clip.game is None for move in plan)
        self.write(f"SCAN COMPLETE\n\n{len(plan)} clips found\n", "muted")
        self.write(f"{ready} READY TO ORGANIZE\n", "ready")
        self.write(f"{unsorted} going to Unsorted\n", "warning" if unsorted else "muted")
        self.write(f"{len(conflicts)} conflicts\n", "warning" if conflicts else "muted")
        renamed = sum(move.destination.name != move.clip.path.name for move in plan if move.status == "READY")
        if renamed:
            self.write(f"{renamed} duplicate name(s) will be renamed safely\n", "ready")
        if destinations:
            self._set_destination_cards([
                (destination, count, "EXISTS" if destination.exists() else "CREATE")
                for destination, count in sorted(destinations.items(), key=lambda item: str(item[0]).lower())
            ])
        if not plan:
            self.write("\nNo video files found outside Organized.\n", "muted")
        elif conflicts:
            self.write("\nCONFLICTS\n", "warning")
            for move in conflicts:
                self.write(f"{move.clip.path.name}\n  {move.status}\n\n", "warning")
        if self.show_details.get() and plan:
            self.write("\nCOMPLETE PLAN\n", "muted")
            for move in plan:
                tag = "ready" if move.status == "READY" else "warning"
                self.write(f"{move.clip.path} -> {move.destination}\n  {move.status}\n\n", tag)
        self.status.set(f"{len(plan)} clips scanned - {ready} ready to organize")
        self._set_signal("[ SCAN COMPLETE ]", ACCENT)
        self._draw_animation_idle("Ready to organize clips")
        self.progress.configure(maximum=max(len(plan), 1))
        self.progress_value.set(len(plan))
        self._set_busy(False)
        self.organize_button.configure(state="normal" if ready else "disabled")

    def organize(self) -> None:
        ready = sum(move.status == "READY" for move in self.plan)
        if not self._confirm(
            "Confirm organization", f"Move {ready} ready file(s)?\n\nConflicts will be skipped.", "Organize"
        ):
            return
        self.events = Queue()
        self.active_operation = "organize"
        self._show_progress()
        self.show_destination_progress = True
        self.destination_progress = {
            destination: 0 for destination, _count, _state in self.destination_cards
        }
        self._draw_destination_cards()
        self._reset_animation("Preparing file moves...")
        self.progress.configure(maximum=max(ready, 1))
        self.progress_value.set(0)
        self._set_busy(True)
        self._set_signal("[ ORGANIZING ]", MUTED)
        self.status.set("Moving files...")
        threading.Thread(target=self._move_worker, daemon=True).start()
        self.after(75, self._poll_events)

    def undo_last(self) -> None:
        history = load_last_operation()
        if history is None:
            self._refresh_undo_button()
            return
        if not self._confirm(
            "Undo last operation",
            f"Move {len(history.moves)} file(s) back from the last {history.operation} operation?\n\n"
            "Files already present at their original locations will be left alone.",
            "Undo",
        ):
            return
        self.events = Queue()
        self.active_operation = "undo"
        self._reset_animation("Undoing the last operation...")
        self._set_signal("[ UNDOING ]", WARNING)
        self.status.set("Moving files back to their original locations...")
        self._set_busy(True)
        threading.Thread(target=self._undo_worker, daemon=True).start()
        self.after(75, self._poll_events)

    def flatten(self) -> None:
        folder = Path(self.directory.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror("Drive Sorter", f"This is not a folder:\n{folder}", parent=self)
            return
        self.events = Queue()
        self.active_operation = "flatten"
        self._show_progress()
        self.progress.configure(maximum=1)
        self.progress_value.set(0)
        self._reset_animation("Building flatten plan...")
        self._set_signal("[ PREPARING FLATTEN ]", WARNING)
        self.status.set("Finding nested video files...")
        self._set_busy(True)
        threading.Thread(target=self._flatten_plan_worker, args=(folder,), daemon=True).start()
        self.after(75, self._poll_events)

    def _flatten_plan_worker(self, folder: Path) -> None:
        try:
            self.events.put(("flatten_plan", build_flatten_plan(folder)))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _show_flatten_plan(self, plan: list[tuple[Path, Path]]) -> None:
        self.flatten_plan = plan
        self._set_busy(False)
        ready = any(move.status == "READY" for move in self.plan)
        self.organize_button.configure(state="normal" if ready else "disabled")
        if not plan:
            self._draw_animation_idle("No nested videos to flatten")
            self._set_signal("[ NOTHING TO FLATTEN ]", MUTED)
            self.status.set("No nested video files found.")
            return

        renamed = sum(source.name != destination.name for source, destination in plan)
        self.clear_output()
        self.write("FLATTEN PLAN\n\n", "warning")
        self.write(f"{len(plan)} nested video file(s) will move to the selected folder.\n", "muted")
        self.write("Existing folders will remain. Files are never overwritten.\n", "muted")
        if renamed:
            self.write(f"{renamed} filename collision(s) will receive a numeric suffix.\n", "warning")
        self._draw_animation_idle("Ready to flatten nested videos")
        if not self._confirm(
            "Confirm flatten all",
            f"Move {len(plan)} nested video file(s) to the selected folder?\n\n"
            "Existing folders stay in place. Filename collisions will be renamed.",
            "Flatten all",
        ):
            self._set_signal("[ FLATTEN CANCELLED ]", MUTED)
            self.status.set("Flatten cancelled. No files moved.")
            return
        self._start_flatten()

    def _start_flatten(self) -> None:
        self.events = Queue()
        self.active_operation = "flatten"
        self._show_progress()
        self.progress.configure(maximum=max(len(self.flatten_plan), 1))
        self.progress_value.set(0)
        self._reset_animation("Flattening nested videos...")
        self._set_signal("[ FLATTENING ]", WARNING)
        self.status.set("Flattening nested video files...")
        self._set_busy(True)
        threading.Thread(target=self._flatten_worker, daemon=True).start()
        self.after(75, self._poll_events)

    def _flatten_worker(self) -> None:
        try:
            moves: list[MoveRecord] = []
            messages = flatten_videos(
                self.flatten_plan, self._report_flatten_progress,
                on_moved=lambda source, destination: moves.append(MoveRecord(source, destination)), echo=False,
            )
            self.events.put(("flatten_complete", (messages, moves)))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _report_flatten_progress(
        self, completed: int, total: int, source: Path, destination: Path, message: str
    ) -> None:
        self.events.put(("flatten_progress", (completed, total, source, destination, message)))

    def _show_flatten_result(self, payload: tuple[list[str], list[MoveRecord]]) -> None:
        messages, moves = payload
        moved = sum(message.startswith("MOVED") for message in messages)
        failed = sum(message.startswith("FAILED") for message in messages)
        self.write("\nFLATTEN RESULT\n", "muted")
        for message in messages:
            if message.startswith("FAILED"):
                self.write(f"{message}\n", "warning")
        if failed:
            summary = f"FLATTEN PARTIALLY COMPLETE: {moved} moved, {failed} failed"
            self._set_signal("[ FLATTEN PARTIALLY COMPLETE ]", WARNING)
        else:
            summary = f"FLATTEN COMPLETE: all {moved} video file(s) moved successfully"
            self._set_signal("[ FLATTEN COMPLETE ]", ACCENT)
        self.write(f"\n{summary}\n", "ready" if not failed else "warning")
        self.status.set(summary + ". Scan to build a new organization plan.")
        self.plan = []
        self.scanned_clips = []
        self._set_busy(False)
        if moves:
            save_last_operation("flatten", moves)
        self._refresh_undo_button()
        self.organize_button.configure(state="disabled")

    def _move_worker(self) -> None:
        try:
            moves: list[MoveRecord] = []
            messages = organize_clips(
                self.plan, self._report_move_progress,
                on_moved=lambda source, destination: moves.append(MoveRecord(source, destination)), echo=False,
            )
            self.events.put(("move_complete", (messages, moves)))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _report_move_progress(self, completed: int, total: int, move: PlannedMove, message: str) -> None:
        self.events.put(("move_progress", (completed, total, move, message)))

    def _show_move_result(self, payload: tuple[list[str], list[MoveRecord]]) -> None:
        messages, moves = payload
        moved = sum(message.startswith("MOVED") for message in messages)
        failed = sum(message.startswith("FAILED") for message in messages)
        skipped = sum(message.startswith("SKIPPED") for message in messages)
        self.write("\nMOVE RESULT\n", "muted")
        for message in messages:
            if not message.startswith("MOVED"):
                self.write(f"{message}\n", "warning")
        if failed or skipped:
            summary = f"PARTIALLY COMPLETE: {moved} moved, {failed} failed, {skipped} skipped"
            self.write(f"\n{summary}\n", "warning")
            self._set_signal("[ ORGANIZATION PARTIALLY COMPLETE ]", WARNING)
        else:
            summary = f"COMPLETE: all {moved} ready file(s) moved successfully"
            self.write(f"\n{summary}\n", "ready")
            self._set_signal("[ ORGANIZATION COMPLETE ]", ACCENT)
        self.status.set(summary + ". Scan again to refresh the plan.")
        if not moved:
            self._draw_animation_idle("No clips were moved")
        self._set_busy(False)
        if moves:
            save_last_operation("organize", moves)
        self._refresh_undo_button()
        self.organize_button.configure(state="disabled")

    def _undo_worker(self) -> None:
        try:
            self.events.put(("undo_complete", undo_last_operation()))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _show_undo_result(self, payload: tuple[list[str], object]) -> None:
        messages, remaining = payload
        moved = sum(message.startswith("UNDONE") for message in messages)
        skipped = sum(message.startswith("SKIPPED") for message in messages)
        failed = sum(message.startswith("FAILED") for message in messages)
        self.plan = []
        self.scanned_clips = []
        self.clear_output()
        self.write("UNDO RESULT\n\n", "muted")
        for message in messages:
            self.write(f"{message}\n", "ready" if message.startswith("UNDONE") else "warning")
        if remaining:
            summary = f"UNDO PARTIALLY COMPLETE: {moved} moved back, {skipped} skipped, {failed} failed"
            self._set_signal("[ UNDO PARTIALLY COMPLETE ]", WARNING)
        else:
            summary = f"UNDO COMPLETE: {moved} file(s) returned to their original locations"
            self._set_signal("[ UNDO COMPLETE ]", ACCENT)
        self.write(f"\n{summary}\n", "ready" if not remaining else "warning")
        self.status.set(summary + ". Scan to refresh the plan.")
        self._draw_animation_idle("Undo complete")
        self._set_busy(False)
        self._refresh_undo_button()
        self.organize_button.configure(state="disabled")


if __name__ == "__main__":
    DriveSorterApp().mainloop()
