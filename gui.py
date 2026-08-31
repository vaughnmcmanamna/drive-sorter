"""A small desktop interface for Drive Sorter."""

from __future__ import annotations

import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from queue import Empty, Queue
from tkinter import filedialog, messagebox, ttk

from metadata_test import PlannedMove, build_plan, file_scanner, organize_clips


BACKGROUND = "#c0c0c0"
PANEL = "#ffffff"
TEXT = "#000000"
MUTED = "#404040"
ACCENT = "#000080"
WARNING = "#804000"
ERROR = "#800000"
FONT = ("MS Sans Serif", 9)


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
        self.plan: list[PlannedMove] = []
        self.scanned_folder: Path | None = None
        self.events: Queue[tuple[str, object]] = Queue()

        style = ttk.Style(self)
        style.theme_use("classic")
        style.configure(
            "DriveSorter.Horizontal.TProgressbar",
            troughcolor="#ffffff", background=ACCENT, bordercolor="#808080", lightcolor=ACCENT,
            darkcolor=ACCENT, thickness=16,
        )
        self._build_interface()

    def _build_interface(self) -> None:
        header = tk.Frame(self, bg=ACCENT, padx=6, pady=4, relief="raised", bd=2)
        header.pack(fill="x")
        tk.Label(header, image=self.header_icon, bg=ACCENT).pack(side="left", padx=(0, 6))
        title_area = tk.Frame(header, bg=ACCENT)
        title_area.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_area, text="Drive Sorter", bg=ACCENT, fg="#ffffff",
            font=("MS Sans Serif", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_area, text="Preview first. Move only after confirmation.", bg=ACCENT,
            fg="#ffffff", font=("MS Sans Serif", 8),
        ).pack(anchor="w")

        controls = tk.LabelFrame(self, text=" Source folder ", bg=BACKGROUND, fg=TEXT, padx=10, pady=10, bd=2, relief="groove", font=FONT)
        controls.pack(fill="x", padx=10, pady=10)
        row = tk.Frame(controls, bg=BACKGROUND)
        row.pack(fill="x")
        self.folder_entry = tk.Entry(
            row, textvariable=self.directory, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="sunken", bd=2, highlightthickness=0, font=FONT,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.browse_button = self._button(row, "Browse", self.choose_folder)
        self.browse_button.pack(side="left", padx=(8, 0))
        self.scan_button = self._button(row, "Scan", self.scan)
        self.scan_button.pack(side="left", padx=(8, 0))
        self.organize_button = self._button(row, "Organize", self.organize)
        self.organize_button.pack(side="left", padx=(8, 0))
        self.organize_button.configure(state="disabled")

        self.progress = ttk.Progressbar(
            controls, mode="determinate", maximum=1, variable=self.progress_value,
            style="DriveSorter.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(10, 0))
        self.signal_label = tk.Label(
            controls, textvariable=self.signal, bg=BACKGROUND, fg=ACCENT,
            font=("MS Sans Serif", 9, "bold"),
        )
        self.signal_label.pack(anchor="w", pady=(10, 0))
        self.details_toggle = tk.Checkbutton(
            controls, text="Show complete plan", variable=self.show_details,
            command=self.refresh_plan, bg=BACKGROUND, fg=MUTED, selectcolor=BACKGROUND,
            activebackground=BACKGROUND, activeforeground=TEXT, font=FONT,
            highlightthickness=0,
        )
        self.details_toggle.pack(anchor="w", pady=(6, 14))

        output_frame = tk.LabelFrame(self, text=" Move plan ", bg=BACKGROUND, fg=TEXT, padx=8, pady=8, bd=2, relief="groove", font=FONT)
        output_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        text_frame = tk.Frame(output_frame, bg=PANEL, relief="sunken", bd=2)
        text_frame.pack(fill="both", expand=True)
        self.output = tk.Text(
            text_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
            padx=8, pady=8, wrap="word", font=FONT, state="disabled",
        )
        scrollbar = tk.Scrollbar(text_frame, command=self.output.yview, relief="flat")
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for tag, color in (("ready", ACCENT), ("warning", WARNING), ("error", ERROR), ("muted", MUTED)):
            self.output.tag_configure(tag, foreground=color)

        footer = tk.Label(self, textvariable=self.status, bg=BACKGROUND, fg=TEXT, font=FONT, relief="sunken", anchor="w", bd=2, padx=6, pady=3)
        footer.pack(fill="x", padx=10, pady=(0, 10))

    def _button(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=BACKGROUND, fg=TEXT,
            activebackground=BACKGROUND, activeforeground=TEXT, disabledforeground="#808080",
            relief="raised", bd=2, padx=10, pady=4, font=FONT,
        )

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.directory.get() or None)
        if chosen:
            self.directory.set(chosen)

    def write(self, text: str, tag: str | None = None) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text, tag)
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _set_signal(self, text: str, color: str) -> None:
        self.signal.set(text)
        self.signal_label.configure(fg=color)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.folder_entry.configure(state=state)
        self.browse_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.details_toggle.configure(state=state)
        if busy:
            self.organize_button.configure(state="disabled")

    def scan(self) -> None:
        folder = Path(self.directory.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror("Drive Sorter", f"This is not a folder:\n{folder}")
            return
        self.plan = []
        self.scanned_folder = folder
        self.events = Queue()
        self.progress.configure(maximum=1)
        self.progress_value.set(0)
        self.clear_output()
        self.write("SCANNING...\n", "muted")
        self._set_signal("[ SCANNING ]", MUTED)
        self.status.set("Reading video metadata...")
        self._set_busy(True)
        threading.Thread(target=self._scan_worker, args=(folder,), daemon=True).start()
        self.after(75, self._poll_events)

    def _scan_worker(self, folder: Path) -> None:
        try:
            output = folder / "Organized"
            self.events.put(("complete", build_plan(file_scanner(folder, output, self._report_scan_progress), output)))
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
                    completed, total, move, _message = payload
                    self.progress.configure(maximum=max(total, 1))
                    self.progress_value.set(completed)
                    self.status.set(f"Moving: {completed}/{total} - {move.clip.path.name}")
                elif event == "complete":
                    self._show_plan(payload)
                    finished = True
                elif event == "move_complete":
                    self._show_move_result(payload)
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

    def refresh_plan(self) -> None:
        if self.plan:
            self._show_plan(self.plan)

    def _show_plan(self, plan: list[PlannedMove]) -> None:
        self.plan = plan
        self.clear_output()
        ready = sum(move.status == "READY" for move in plan)
        conflicts = [move for move in plan if move.status != "READY"]
        destinations = Counter(move.destination.parent for move in plan if move.status == "READY")
        unsorted = sum(move.clip.game is None for move in plan)
        self.write(f"SCAN COMPLETE\n\n{len(plan)} clips found\n", "muted")
        self.write(f"{ready} READY TO ORGANIZE\n", "ready")
        self.write(f"{unsorted} going to Unsorted\n", "warning" if unsorted else "muted")
        self.write(f"{len(conflicts)} conflicts\n", "warning" if conflicts else "muted")
        if destinations:
            self.write("\nREADY DESTINATIONS\n", "muted")
            root = (self.scanned_folder or Path(self.directory.get()).expanduser()) / "Organized"
            for destination, count in sorted(destinations.items(), key=lambda item: str(item[0]).lower()):
                try:
                    label = destination.relative_to(root)
                except ValueError:
                    label = destination
                state = "EXISTS" if destination.exists() else "CREATE"
                tag = "muted" if state == "EXISTS" else "ready"
                self.write(f"{label} - {count} file(s) - {state}\n", tag)
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
        self.progress.configure(maximum=max(len(plan), 1))
        self.progress_value.set(len(plan))
        self._set_busy(False)
        self.organize_button.configure(state="normal" if ready else "disabled")

    def organize(self) -> None:
        ready = sum(move.status == "READY" for move in self.plan)
        if not messagebox.askyesno("Confirm organization", f"Move {ready} ready file(s)?\n\nConflicts will be skipped."):
            return
        self.events = Queue()
        self.progress.configure(maximum=max(ready, 1))
        self.progress_value.set(0)
        self._set_busy(True)
        self._set_signal("[ ORGANIZING ]", MUTED)
        self.status.set("Moving files...")
        threading.Thread(target=self._move_worker, daemon=True).start()
        self.after(75, self._poll_events)

    def _move_worker(self) -> None:
        try:
            self.events.put(("move_complete", organize_clips(self.plan, self._report_move_progress, echo=False)))
        except Exception as error:
            self.events.put(("failed", str(error)))

    def _report_move_progress(self, completed: int, total: int, move: PlannedMove, message: str) -> None:
        self.events.put(("move_progress", (completed, total, move, message)))

    def _show_move_result(self, messages: list[str]) -> None:
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
        self._set_busy(False)
        self.organize_button.configure(state="disabled")


if __name__ == "__main__":
    DriveSorterApp().mainloop()
