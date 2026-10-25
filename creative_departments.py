"""
Video Studio and 2D Animation Studio for Homework & Document Studio.

Design principles
─────────────────
• Zero top-level optional imports — Pillow, ffmpeg etc. are checked at
  the moment they are actually needed, so the app always starts cleanly.
• Every project is saved as a portable JSON file (.hvs / .has).
• Rendering uses ffmpeg when it is on PATH; otherwise the project is kept
  editable and re-renderable whenever ffmpeg is installed later.
• Animated GIF export works with Pillow only (no ffmpeg needed).
• All media stays local.  No cloud calls are made anywhere.
"""
from __future__ import annotations

import copy
import json
import math
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from typing import Optional

# ─── project format tags ──────────────────────────────────────────────────────
VIDEO_FORMAT = "HomeworkVideoStudio"
ANIM_FORMAT  = "HomeworkAnimationStudio"


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _pil_available() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("PIL") is not None
    except Exception:
        return False


def _ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO STUDIO
# ══════════════════════════════════════════════════════════════════════════════

class VideoStudio(tk.Toplevel):
    """
    Full-featured non-linear video editor.

    Features
    ─────────
    • Multi-track timeline  (video, audio, titles, effects)
    • Per-clip trim, speed, volume, opacity
    • Transitions: Cut / Fade / Dissolve / Slide / Zoom / Blur
    • Color grading (brightness, contrast, saturation, hue)
    • Caption / subtitle track with time codes
    • Markers on the timeline
    • Preview: image clips show thumbnails, video clips show file info
    • Audio waveform placeholder
    • Render to MP4 via ffmpeg (concat or re-encode)
    • Project save / open  (.hvs)
    • Keyboard shortcuts
    """

    _TRANSITIONS = ["Cut", "Fade", "Dissolve", "Slide left", "Slide right",
                    "Zoom in", "Zoom out", "Blur"]
    _TRACK_KINDS = ["video", "audio", "title", "effect", "image"]
    _FILTERS = ["None", "Grayscale", "Sepia", "Vignette", "Sharpen",
                "Blur (soft)", "Brightness+", "Contrast+", "Vintage",
                "Cool tone", "Warm tone"]

    # ── project skeleton ──────────────────────────────────────────────────────

    def _empty_project(self) -> dict:
        return {
            "format": VIDEO_FORMAT, "version": 3,
            "title": "Untitled Video",
            "size": "1920x1080", "fps": 30,
            "tracks": [
                {"id": "v1", "kind": "video", "name": "Video 1",
                 "clips": [], "muted": False, "locked": False, "color": "#315C8A"},
                {"id": "v2", "kind": "video", "name": "Video 2",
                 "clips": [], "muted": False, "locked": False, "color": "#1D4E89"},
                {"id": "a1", "kind": "audio", "name": "Audio 1",
                 "clips": [], "muted": False, "locked": False, "color": "#547A5D"},
                {"id": "a2", "kind": "audio", "name": "Audio 2",
                 "clips": [], "muted": False, "locked": False, "color": "#2D6A4F"},
                {"id": "t1", "kind": "title", "name": "Titles",
                 "clips": [], "muted": False, "locked": False, "color": "#7B5AA6"},
                {"id": "e1", "kind": "effect", "name": "Effects",
                 "clips": [], "muted": False, "locked": False, "color": "#C0392B"},
            ],
            "markers": [],
            "captions": [],
            "metadata": {},
        }

    def _empty_clip(self, path: str) -> dict:
        return {
            "path": path,
            "start": "0", "end": "",
            "offset": 0.0,
            "volume": 1.0, "opacity": 1.0, "speed": 1.0,
            "transition": "Cut", "transition_duration": 0.5,
            "muted": False, "label": "",
            "filter": "None",
            "color_grading": {
                "brightness": 0, "contrast": 0,
                "saturation": 0, "hue": 0, "temperature": 0,
            },
        }

    # ── init ──────────────────────────────────────────────────────────────────

    def __init__(self, master):
        super().__init__(master)
        self.title("Video Studio")
        self.geometry("1380x820")
        self.minsize(980, 600)
        self.project = self._empty_project()
        self.selected_track = 0
        self.selected_clip: Optional[int] = None
        self.playhead = tk.DoubleVar(value=0.0)
        self._playing = False
        self._preview_image = None   # keep reference so GC doesn't kill it
        self._build()
        self._refresh_all()
        self._bind_keys()

    # ── keyboard ──────────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.bind("<space>",      lambda e: self._toggle_play())
        self.bind("<Delete>",     lambda e: self._remove_clip())
        self.bind("<Control-s>",  lambda e: self._save())
        self.bind("<Control-o>",  lambda e: self._open())
        self.bind("<Control-n>",  lambda e: self._new())
        self.bind("<Left>",       lambda e: self._nudge(-1))
        self.bind("<Right>",      lambda e: self._nudge(1))

    def _nudge(self, d: int):
        pass  # could move playhead / trim point

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── toolbar ───────────────────────────────────────────────────────────
        tb = ttk.Frame(self)
        tb.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(tb, text="VIDEO STUDIO",
                  font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 14))

        for label, cmd in [
            ("New",           self._new),
            ("Open…",         self._open),
            ("Save",          self._save),
            ("Add clips",     self._add_clips),
            ("Add audio",     self._add_audio),
            ("Add title",     self._add_title_clip),
            ("Add marker",    self._add_marker),
            ("Add track",     self._add_track),
            ("Project info",  self._project_info),
            ("Render MP4",    self._render),
            ("Export audio",  self._export_audio),
        ]:
            ttk.Button(tb, text=label, command=cmd).pack(side="right", padx=2)

        # ── body ──────────────────────────────────────────────────────────────
        pw = ttk.Panedwindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=8, pady=6)

        left   = ttk.Frame(pw, width=230)
        center = ttk.Frame(pw)
        right  = ttk.Frame(pw, width=270)
        pw.add(left,   weight=0)
        pw.add(center, weight=1)
        pw.add(right,  weight=0)

        self._build_left(left)
        self._build_center(center)
        self._build_right(right)

        # ── status bar ────────────────────────────────────────────────────────
        sb = ttk.Frame(self)
        sb.pack(fill="x", padx=8, pady=(0, 6))
        self._status = tk.StringVar(value="Ready — add clips to begin")
        ttk.Label(sb, textvariable=self._status).pack(side="left")
        ttk.Label(sb, text="Space=play/pause  Delete=remove  Ctrl+S=save",
                  foreground="#94a3b8").pack(side="right")

    def _build_left(self, parent):
        ttk.Label(parent, text="Tracks", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(4, 2), padx=4)
        self._track_list = tk.Listbox(parent, exportselection=False,
                                      activestyle="none")
        self._track_list.pack(fill="both", expand=True, padx=4)
        self._track_list.bind("<<ListboxSelect>>", self._on_track_select)

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=4, pady=4)
        for t, c in [("Mute", self._mute_track), ("Lock", self._lock_track),
                      ("Remove", self._remove_track)]:
            ttk.Button(row, text=t, command=c).pack(side="left", padx=1)

        ttk.Separator(parent).pack(fill="x", padx=4, pady=6)
        ttk.Label(parent, text="Clips in track",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=4)
        self._clip_list = tk.Listbox(parent, exportselection=False,
                                     activestyle="none")
        self._clip_list.pack(fill="both", expand=True, padx=4)
        self._clip_list.bind("<<ListboxSelect>>", self._on_clip_select)

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", padx=4, pady=4)
        for t, c in [("↑", lambda: self._move_clip(-1)),
                      ("↓", lambda: self._move_clip(1)),
                      ("Remove", self._remove_clip)]:
            ttk.Button(row2, text=t, command=c).pack(side="left", padx=1)

    def _build_center(self, parent):
        # Preview canvas
        self._preview = tk.Canvas(parent, bg="#0d1117",
                                  highlightthickness=0, height=380)
        self._preview.pack(fill="x")
        self._preview.create_text(
            540, 190,
            text="Add clips →  preview will appear here\n\n"
                 "Video Studio  •  All media stays on your computer",
            fill="#c9d1d9", font=("Segoe UI", 16), justify="center",
            tags="welcome")

        # Transport / playhead
        tf = ttk.Frame(parent)
        tf.pack(fill="x", padx=4, pady=4)
        ttk.Button(tf, text="⏮", width=3,
                   command=lambda: self.playhead.set(0)).pack(side="left")
        ttk.Button(tf, text="⏪", width=3,
                   command=lambda: self._nudge(-1)).pack(side="left")
        self._play_btn = ttk.Button(tf, text="▶ Play",
                                    command=self._toggle_play)
        self._play_btn.pack(side="left", padx=4)
        ttk.Button(tf, text="⏩", width=3,
                   command=lambda: self._nudge(1)).pack(side="left")
        ttk.Label(tf, text="Playhead:").pack(side="left", padx=(12, 2))
        self._playhead_label = ttk.Label(tf, text="0.00 s")
        self._playhead_label.pack(side="left")

        # Timeline canvas
        tl_frame = ttk.Frame(parent)
        tl_frame.pack(fill="both", expand=True, padx=4, pady=(2, 0))
        ttk.Label(tl_frame, text="Timeline",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._tl_canvas = tk.Canvas(tl_frame, bg="#1e2636",
                                    highlightthickness=0)
        tl_sb_h = ttk.Scrollbar(tl_frame, orient="horizontal",
                                 command=self._tl_canvas.xview)
        tl_sb_v = ttk.Scrollbar(tl_frame, orient="vertical",
                                 command=self._tl_canvas.yview)
        self._tl_canvas.configure(xscrollcommand=tl_sb_h.set,
                                   yscrollcommand=tl_sb_v.set)
        tl_sb_h.pack(side="bottom", fill="x")
        tl_sb_v.pack(side="right",  fill="y")
        self._tl_canvas.pack(side="left", fill="both", expand=True)
        self._tl_canvas.bind("<Configure>", lambda e: self._draw_timeline())
        self._tl_canvas.bind("<Button-1>",  self._tl_click)

    def _build_right(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)

        clip_tab  = ttk.Frame(nb)
        grade_tab = ttk.Frame(nb)
        cap_tab   = ttk.Frame(nb)
        nb.add(clip_tab,  text="Clip")
        nb.add(grade_tab, text="Color")
        nb.add(cap_tab,   text="Captions")

        # ── Clip tab ──────────────────────────────────────────────────────────
        self._clip_name = tk.StringVar(value="Select a clip")
        ttk.Label(clip_tab, textvariable=self._clip_name,
                  font=("Segoe UI", 10, "bold"),
                  wraplength=230).pack(anchor="w", padx=8, pady=(8, 2))

        self._clip_label = tk.StringVar()
        ttk.Label(clip_tab, text="Label").pack(anchor="w", padx=8)
        ttk.Entry(clip_tab, textvariable=self._clip_label).pack(
            fill="x", padx=8, pady=(0, 6))

        self._trim_start  = tk.StringVar(value="0")
        self._trim_end    = tk.StringVar(value="")
        self._clip_speed  = tk.DoubleVar(value=1.0)
        self._clip_volume = tk.DoubleVar(value=1.0)
        self._clip_opac   = tk.DoubleVar(value=1.0)
        self._clip_muted  = tk.BooleanVar(value=False)
        self._clip_trans  = tk.StringVar(value="Cut")
        self._clip_trans_dur = tk.DoubleVar(value=0.5)
        self._clip_filter = tk.StringVar(value="None")

        fields = [
            ("Trim start (s)", self._trim_start, "entry"),
            ("Trim end (s)",   self._trim_end,   "entry"),
            ("Speed (0.25–4)", self._clip_speed, "spin"),
            ("Volume (0–1)",   self._clip_volume,"spin"),
            ("Opacity (0–1)",  self._clip_opac,  "spin"),
        ]
        for label, var, kind in fields:
            ttk.Label(clip_tab, text=label).pack(anchor="w", padx=8)
            if kind == "entry":
                ttk.Entry(clip_tab, textvariable=var).pack(
                    fill="x", padx=8, pady=(0, 4))
            else:
                ttk.Spinbox(clip_tab, from_=0.0, to=4.0,
                            increment=0.05, textvariable=var,
                            width=9).pack(anchor="w", padx=8, pady=(0, 4))

        ttk.Checkbutton(clip_tab, text="Mute this clip",
                        variable=self._clip_muted).pack(anchor="w", padx=8)

        ttk.Label(clip_tab, text="Transition in").pack(
            anchor="w", padx=8, pady=(6, 0))
        ttk.Combobox(clip_tab, textvariable=self._clip_trans,
                     values=self._TRANSITIONS,
                     state="readonly").pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(clip_tab, text="Transition duration (s)").pack(
            anchor="w", padx=8)
        ttk.Spinbox(clip_tab, from_=0.1, to=5.0,
                    increment=0.1, textvariable=self._clip_trans_dur,
                    width=9).pack(anchor="w", padx=8, pady=(0, 4))

        ttk.Label(clip_tab, text="Filter").pack(anchor="w", padx=8)
        ttk.Combobox(clip_tab, textvariable=self._clip_filter,
                     values=self._FILTERS,
                     state="readonly").pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(clip_tab, text="Apply clip changes",
                   command=self._apply_clip).pack(fill="x", padx=8, pady=4)
        ttk.Button(clip_tab, text="Preview this clip",
                   command=self._preview_selected).pack(fill="x", padx=8)

        # ── Color grading tab ─────────────────────────────────────────────────
        ttk.Label(grade_tab, text="Color grading (current clip)",
                  font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        self._grade_vars = {}
        for name in ("brightness", "contrast", "saturation", "hue", "temperature"):
            ttk.Label(grade_tab, text=name.capitalize()).pack(
                anchor="w", padx=8)
            v = tk.DoubleVar(value=0.0)
            self._grade_vars[name] = v
            s = tk.Scale(grade_tab, variable=v, from_=-100, to=100,
                         orient="horizontal", resolution=1,
                         bg=self.cget("bg"), highlightthickness=0)
            s.pack(fill="x", padx=8, pady=(0, 3))
        ttk.Button(grade_tab, text="Apply color grade",
                   command=self._apply_color_grade).pack(
            fill="x", padx=8, pady=8)
        ttk.Button(grade_tab, text="Reset color grade",
                   command=self._reset_color_grade).pack(fill="x", padx=8)

        # ── Captions tab ──────────────────────────────────────────────────────
        ttk.Label(cap_tab, text="Captions / subtitles",
                  font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        ttk.Label(cap_tab,
                  text="Text to appear at the selected clip's position:",
                  wraplength=230).pack(anchor="w", padx=8)
        self._cap_text = tk.Text(cap_tab, height=4, wrap="word")
        self._cap_text.pack(fill="x", padx=8, pady=4)
        self._cap_time_start = tk.DoubleVar(value=0.0)
        self._cap_time_end   = tk.DoubleVar(value=3.0)
        for label, var in [("Start time (s)", self._cap_time_start),
                            ("End time (s)",   self._cap_time_end)]:
            ttk.Label(cap_tab, text=label).pack(anchor="w", padx=8)
            ttk.Spinbox(cap_tab, from_=0.0, to=9999.0,
                        increment=0.1, textvariable=var,
                        width=10).pack(anchor="w", padx=8, pady=(0, 4))
        ttk.Button(cap_tab, text="Add caption",
                   command=self._add_caption).pack(fill="x", padx=8, pady=4)
        self._cap_list = tk.Listbox(cap_tab, height=8, exportselection=False)
        self._cap_list.pack(fill="both", expand=True, padx=8)
        ttk.Button(cap_tab, text="Delete selected caption",
                   command=self._del_caption).pack(fill="x", padx=8, pady=4)
        ttk.Button(cap_tab, text="Export SRT",
                   command=self._export_srt).pack(fill="x", padx=8)

    # ── refresh helpers ───────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_track_list()
        self._refresh_clip_list()
        self._draw_timeline()
        self._refresh_captions()

    def _refresh_track_list(self):
        self._track_list.delete(0, "end")
        for t in self.project["tracks"]:
            icon = "🔇" if t.get("muted") else ("🔒" if t.get("locked") else "▶")
            self._track_list.insert("end",
                f"{icon} {t['name']}  [{t['kind']}]  "
                f"({len(t['clips'])} clips)")
        if self.selected_track < self._track_list.size():
            self._track_list.selection_set(self.selected_track)

    def _refresh_clip_list(self):
        self._clip_list.delete(0, "end")
        track = self._current_track()
        if track is None:
            return
        for i, c in enumerate(track["clips"]):
            name = Path(c["path"]).name
            label = f"  [{c['label']}]" if c.get("label") else ""
            self._clip_list.insert("end",
                f"{i+1:02d}  {name}  "
                f"[{c.get('transition','Cut')}]{label}")
        if (self.selected_clip is not None
                and self.selected_clip < self._clip_list.size()):
            self._clip_list.selection_set(self.selected_clip)

    def _refresh_captions(self):
        if not hasattr(self, "_cap_list"):
            return
        self._cap_list.delete(0, "end")
        for cap in self.project.get("captions", []):
            self._cap_list.insert(
                "end",
                f"{cap.get('start',0):.1f}–{cap.get('end',3):.1f}s  "
                f"{cap.get('text','')[:40]}")

    def _draw_timeline(self):
        c = self._tl_canvas
        c.delete("all")
        W = max(800, c.winfo_width())
        tracks = self.project["tracks"]
        ROW_H   = 44
        LABEL_W = 90
        RULER_H = 22
        total_h = RULER_H + ROW_H * len(tracks) + 40

        # ruler
        c.create_rectangle(0, 0, W, RULER_H, fill="#111827", outline="")
        for sec in range(0, 600, 5):
            rx = LABEL_W + sec * 24
            c.create_line(rx, 0, rx, RULER_H, fill="#374151")
            c.create_text(rx + 3, 4, text=f"{sec}s", anchor="nw",
                          fill="#9ca3af", font=("Segoe UI", 7))

        # playhead
        px = LABEL_W + self.playhead.get() * 24
        c.create_line(px, 0, px, total_h, fill="#F4B544", width=2, tags="ph")

        # track rows
        for row_idx, track in enumerate(tracks):
            y0 = RULER_H + row_idx * ROW_H
            y1 = y0 + ROW_H - 2
            row_color = "#1e2a3a" if row_idx % 2 == 0 else "#182031"
            c.create_rectangle(0, y0, W, y1, fill=row_color, outline="")
            c.create_rectangle(0, y0, LABEL_W, y1,
                               fill="#111827", outline="")
            icon = "🔇" if track.get("muted") else "▶"
            c.create_text(6, y0 + ROW_H // 2, text=icon + " " + track["name"],
                          anchor="w", fill="#cbd5e1",
                          font=("Segoe UI", 8, "bold"))

            tc = track.get("color", "#315C8A")
            for ci, clip in enumerate(track["clips"]):
                try:
                    cstart = float(clip.get("offset", ci * 5))
                    cdur   = float(clip.get("end", 5) or 5) - float(clip.get("start", 0) or 0)
                    if cdur <= 0:
                        cdur = 5
                except Exception:
                    cstart, cdur = ci * 5, 5
                cx0 = LABEL_W + int(cstart * 24)
                cx1 = cx0 + max(20, int(cdur * 24))
                is_sel = (row_idx == self.selected_track
                          and ci == self.selected_clip)
                fill = "#F4B544" if is_sel else tc
                c.create_rectangle(cx0 + 1, y0 + 4, cx1 - 1, y1 - 4,
                                   fill=fill, outline="white" if is_sel else "")
                label = Path(clip["path"]).stem[:18]
                c.create_text(cx0 + 4, y0 + ROW_H // 2, text=label,
                              anchor="w", fill="white",
                              font=("Segoe UI", 7))

        # markers
        for m in self.project.get("markers", []):
            mx = LABEL_W + m["time"] * 24
            c.create_line(mx, RULER_H, mx, total_h, fill=m.get("color", "#F4B544"),
                          dash=(4, 2), width=1)
            c.create_text(mx + 2, RULER_H + 2, text=m.get("label", ""),
                          anchor="nw", fill="#fbbf24", font=("Segoe UI", 7))

        c.configure(scrollregion=(0, 0, max(W, LABEL_W + 600 * 24), total_h))

    def _tl_click(self, e):
        LABEL_W = 90
        RULER_H = 22
        ROW_H   = 44
        if e.x > LABEL_W:
            t = (e.x - LABEL_W) / 24
            self.playhead.set(max(0.0, t))
            self._playhead_label.configure(text=f"{t:.2f} s")
            self._draw_timeline()
        row = (e.y - RULER_H) // ROW_H
        if 0 <= row < len(self.project["tracks"]):
            self.selected_track = row
            self.selected_clip  = None
            self._refresh_track_list()
            self._refresh_clip_list()

    # ── event handlers ────────────────────────────────────────────────────────

    def _on_track_select(self, _e=None):
        s = self._track_list.curselection()
        if s:
            self.selected_track = s[0]
            self.selected_clip  = None
            self._refresh_clip_list()
            self._draw_timeline()

    def _on_clip_select(self, _e=None):
        s = self._clip_list.curselection()
        if not s:
            return
        self.selected_clip = s[0]
        track = self._current_track()
        if track is None or self.selected_clip >= len(track["clips"]):
            return
        clip = track["clips"][self.selected_clip]
        self._clip_name.set(Path(clip["path"]).name)
        self._clip_label.set(clip.get("label", ""))
        self._trim_start.set(clip.get("start", "0"))
        self._trim_end.set(clip.get("end", ""))
        self._clip_speed.set(clip.get("speed", 1.0))
        self._clip_volume.set(clip.get("volume", 1.0))
        self._clip_opac.set(clip.get("opacity", 1.0))
        self._clip_muted.set(clip.get("muted", False))
        self._clip_trans.set(clip.get("transition", "Cut"))
        self._clip_trans_dur.set(clip.get("transition_duration", 0.5))
        self._clip_filter.set(clip.get("filter", "None"))
        cg = clip.get("color_grading", {})
        for k, v in self._grade_vars.items():
            v.set(cg.get(k, 0))
        self._draw_timeline()
        self._preview_selected()

    def _apply_clip(self):
        track = self._current_track()
        if track is None or self.selected_clip is None:
            return
        if self.selected_clip >= len(track["clips"]):
            return
        clip = track["clips"][self.selected_clip]
        clip.update({
            "label":               self._clip_label.get(),
            "start":               self._trim_start.get(),
            "end":                 self._trim_end.get(),
            "speed":               self._clip_speed.get(),
            "volume":              self._clip_volume.get(),
            "opacity":             self._clip_opac.get(),
            "muted":               self._clip_muted.get(),
            "transition":          self._clip_trans.get(),
            "transition_duration": self._clip_trans_dur.get(),
            "filter":              self._clip_filter.get(),
        })
        self._refresh_clip_list()
        self._draw_timeline()
        self._status.set("Clip updated.")

    def _apply_color_grade(self):
        track = self._current_track()
        if track is None or self.selected_clip is None:
            return
        clip = track["clips"][self.selected_clip]
        clip["color_grading"] = {k: v.get() for k, v in self._grade_vars.items()}
        self._status.set("Color grade applied.")

    def _reset_color_grade(self):
        for v in self._grade_vars.values():
            v.set(0.0)
        self._apply_color_grade()

    def _preview_selected(self):
        self._preview.delete("all")
        self._preview_image = None
        track = self._current_track()
        if track is None or self.selected_clip is None:
            return
        if self.selected_clip >= len(track["clips"]):
            return
        clip = track["clips"][self.selected_clip]
        path = clip["path"]
        suffix = Path(path).suffix.lower()
        cw = max(200, self._preview.winfo_width())
        ch = max(100, self._preview.winfo_height())

        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            try:
                from PIL import Image, ImageTk, ImageEnhance
                im = Image.open(path)
                # Apply color grading for preview
                cg = clip.get("color_grading", {})
                if cg.get("brightness", 0) != 0:
                    im = ImageEnhance.Brightness(im).enhance(
                        1 + cg["brightness"] / 100)
                if cg.get("contrast", 0) != 0:
                    im = ImageEnhance.Contrast(im).enhance(
                        1 + cg["contrast"] / 100)
                if cg.get("saturation", 0) != 0:
                    im = ImageEnhance.Color(im).enhance(
                        1 + cg["saturation"] / 100)
                filt = clip.get("filter", "None")
                if filt == "Grayscale":
                    im = im.convert("L").convert("RGB")
                elif filt == "Sepia":
                    im = im.convert("L").convert("RGB")
                im.thumbnail((cw, ch))
                self._preview_image = ImageTk.PhotoImage(im)
                self._preview.create_image(cw // 2, ch // 2,
                                           image=self._preview_image)
                return
            except Exception:
                pass
        # fallback info card
        self._preview.create_rectangle(0, 0, cw, ch, fill="#0d1117")
        size_str = ""
        try:
            size_str = f"\nSize: {Path(path).stat().st_size // 1024} KB"
        except Exception:
            pass
        self._preview.create_text(
            cw // 2, ch // 2,
            text=f"{Path(path).name}\n{suffix[1:].upper()} file{size_str}\n\n"
                 f"Transition: {clip.get('transition','Cut')}  "
                 f"Filter: {clip.get('filter','None')}",
            fill="#c9d1d9", font=("Segoe UI", 13), justify="center")

    # ── actions ───────────────────────────────────────────────────────────────

    def _current_track(self) -> Optional[dict]:
        tracks = self.project["tracks"]
        if 0 <= self.selected_track < len(tracks):
            return tracks[self.selected_track]
        return None

    def _add_clips(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="Add video or image clips",
            filetypes=[("Video and images",
                        "*.mp4 *.mov *.mkv *.avi *.webm "
                        "*.png *.jpg *.jpeg *.webp *.gif")])
        if not paths:
            return
        track = self._current_track()
        if track is None:
            return
        for p in paths:
            clip = self._empty_clip(p)
            clip["offset"] = len(track["clips"]) * 5.0
            track["clips"].append(clip)
        self._refresh_all()
        self._status.set(f"Added {len(paths)} clip(s) to {track['name']}.")

    def _add_audio(self):
        p = filedialog.askopenfilename(
            parent=self, title="Add audio track",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac")])
        if not p:
            return
        # put in first audio track
        audio_track = next(
            (t for t in self.project["tracks"] if t["kind"] == "audio"), None)
        if audio_track is None:
            audio_track = self._add_track_obj("Audio", "audio")
        clip = self._empty_clip(p)
        audio_track["clips"].append(clip)
        self._refresh_all()
        self._status.set(f"Audio added: {Path(p).name}")

    def _add_title_clip(self):
        text = simpledialog.askstring(
            "Add title", "Title text:", parent=self)
        if not text:
            return
        title_track = next(
            (t for t in self.project["tracks"] if t["kind"] == "title"), None)
        if title_track is None:
            title_track = self._add_track_obj("Titles", "title")
        clip = {
            "path": "",
            "text": text,
            "start": "0", "end": "5",
            "offset": 0.0,
            "transition": "Fade",
            "transition_duration": 0.5,
            "label": text[:30],
            "volume": 0.0, "opacity": 1.0, "speed": 1.0,
            "muted": True, "filter": "None",
            "color_grading": {},
        }
        title_track["clips"].append(clip)
        self._refresh_all()
        self._status.set("Title clip added.")

    def _add_marker(self):
        time = simpledialog.askfloat(
            "Add marker", "Time (seconds):", initialvalue=0.0, parent=self)
        if time is None:
            return
        label = simpledialog.askstring(
            "Marker label", "Optional label:", parent=self) or ""
        self.project["markers"].append(
            {"time": time, "label": label, "color": "#F4B544"})
        self._draw_timeline()
        self._status.set(f"Marker added at {time:.1f}s")

    def _add_track(self):
        name = simpledialog.askstring(
            "Add track", "Track name:", parent=self) or "New Track"
        kinds = ["video", "audio", "title", "effect", "image"]
        kind = simpledialog.askstring(
            "Track type",
            "Type: video / audio / title / effect / image",
            initialvalue="video", parent=self) or "video"
        kind = kind.lower()
        if kind not in kinds:
            kind = "video"
        self._add_track_obj(name, kind)
        self._refresh_all()

    def _add_track_obj(self, name: str, kind: str) -> dict:
        colors = {"video": "#315C8A", "audio": "#547A5D",
                  "title": "#7B5AA6", "effect": "#C0392B",
                  "image": "#D97706"}
        track = {"id": new_id(), "kind": kind, "name": name,
                 "clips": [], "muted": False, "locked": False,
                 "color": colors.get(kind, "#315C8A")}
        self.project["tracks"].append(track)
        return track

    def _remove_track(self):
        track = self._current_track()
        if track is None:
            return
        if not messagebox.askyesno("Remove track",
                                   f"Remove {track['name']} and all its clips?",
                                   parent=self):
            return
        self.project["tracks"].pop(self.selected_track)
        self.selected_track = max(0, self.selected_track - 1)
        self._refresh_all()

    def _mute_track(self):
        track = self._current_track()
        if track:
            track["muted"] = not track.get("muted", False)
            self._refresh_all()

    def _lock_track(self):
        track = self._current_track()
        if track:
            track["locked"] = not track.get("locked", False)
            self._refresh_all()

    def _remove_clip(self):
        track = self._current_track()
        if track and self.selected_clip is not None:
            if 0 <= self.selected_clip < len(track["clips"]):
                track["clips"].pop(self.selected_clip)
                self.selected_clip = None
                self._refresh_all()

    def _move_clip(self, d: int):
        track = self._current_track()
        if track is None or self.selected_clip is None:
            return
        clips = track["clips"]
        n = self.selected_clip + d
        if 0 <= n < len(clips):
            clips[self.selected_clip], clips[n] = clips[n], clips[self.selected_clip]
            self.selected_clip = n
            self._refresh_all()
            self._clip_list.selection_set(n)

    def _add_caption(self):
        text = self._cap_text.get("1.0", "end-1c").strip()
        if not text:
            return
        cap = {
            "text":  text,
            "start": self._cap_time_start.get(),
            "end":   self._cap_time_end.get(),
            "clip":  self.selected_clip or 0,
        }
        self.project["captions"].append(cap)
        self._cap_text.delete("1.0", "end")
        self._refresh_captions()
        self._draw_timeline()
        self._status.set("Caption added.")

    def _del_caption(self):
        s = self._cap_list.curselection()
        if s:
            self.project["captions"].pop(s[0])
            self._refresh_captions()

    def _export_srt(self):
        p = filedialog.asksaveasfilename(
            parent=self, defaultextension=".srt",
            filetypes=[("SubRip subtitle", "*.srt")])
        if not p:
            return
        lines = []
        for i, cap in enumerate(self.project.get("captions", []), 1):
            def _t(s):
                h = int(s) // 3600
                m = (int(s) % 3600) // 60
                sec = s % 60
                return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")
            lines.append(str(i))
            lines.append(f"{_t(cap.get('start',0))} --> {_t(cap.get('end',3))}")
            lines.append(cap.get("text", ""))
            lines.append("")
        Path(p).write_text("\n".join(lines), encoding="utf-8")
        self._status.set(f"SRT exported: {Path(p).name}")

    def _toggle_play(self):
        self._playing = not self._playing
        self._play_btn.configure(text="⏸ Pause" if self._playing else "▶ Play")
        if self._playing:
            self._do_play()

    def _do_play(self):
        if not self._playing:
            return
        t = self.playhead.get() + 0.1
        if t > 300:
            t = 0
        self.playhead.set(t)
        self._playhead_label.configure(text=f"{t:.2f} s")
        self._draw_timeline()
        self.after(100, self._do_play)

    def _project_info(self):
        win = tk.Toplevel(self)
        win.title("Project info")
        win.transient(self)
        ttk.Label(win, text="Project settings",
                  font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")
        title_var = tk.StringVar(value=self.project.get("title", ""))
        size_var  = tk.StringVar(value=self.project.get("size", "1920x1080"))
        fps_var   = tk.IntVar(value=self.project.get("fps", 30))
        for row, label, var, values in [
            (1, "Title",     title_var, None),
            (2, "Frame size", size_var,
             ["1920x1080","1280x720","3840x2160","1080x1920","1080x1080"]),
            (3, "FPS",       fps_var,  None),
        ]:
            ttk.Label(win, text=label).grid(row=row, column=0,
                                             padx=16, pady=4, sticky="w")
            if values:
                ttk.Combobox(win, textvariable=var, values=values,
                             state="readonly", width=22).grid(
                    row=row, column=1, padx=16, pady=4)
            elif isinstance(var, tk.IntVar):
                ttk.Spinbox(win, from_=1, to=120, textvariable=var,
                            width=8).grid(row=row, column=1,
                                          padx=16, pady=4, sticky="w")
            else:
                ttk.Entry(win, textvariable=var, width=25).grid(
                    row=row, column=1, padx=16, pady=4)

        def apply():
            self.project["title"] = title_var.get()
            self.project["size"]  = size_var.get()
            self.project["fps"]   = fps_var.get()
            self.title(f"Video Studio — {title_var.get()}")
            win.destroy()
            self._status.set("Project info updated.")

        ttk.Button(win, text="Apply", command=apply).grid(
            row=4, column=0, columnspan=2, padx=16, pady=(8, 16), sticky="ew")

    # ── render ────────────────────────────────────────────────────────────────

    def _render(self):
        ff = _ffmpeg()
        if not ff:
            messagebox.showinfo(
                "ffmpeg not found",
                "Your project is saved and fully editable.\n\n"
                "Install ffmpeg (https://ffmpeg.org/download.html), add it to "
                "PATH, then click Render MP4 again.\n\n"
                "On Windows: winget install ffmpeg",
                parent=self)
            return

        all_clips = []
        for t in self.project["tracks"]:
            if t["kind"] == "video" and not t.get("muted"):
                all_clips.extend(c for c in t["clips"]
                                 if Path(c.get("path", "")).exists())
        if not all_clips:
            messagebox.showinfo("No video clips",
                                "Add video clips to a video track first.",
                                parent=self)
            return
        out = filedialog.asksaveasfilename(
            parent=self, defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")])
        if not out:
            return
        manifest = Path(tempfile.gettempdir()) / "studio_concat.txt"
        lines = [f"file '{c['path'].replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'"
                 for c in all_clips]
        manifest.write_text("\n".join(lines), encoding="utf-8")
        try:
            result = subprocess.run(
                [ff, "-y", "-f", "concat", "-safe", "0",
                 "-i", str(manifest), "-c", "copy", out],
                check=True, capture_output=True)
            self._status.set(f"Rendered: {Path(out).name}")
            messagebox.showinfo("Render complete",
                                f"MP4 saved:\n{out}", parent=self)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or b"").decode(errors="replace")[:400]
            messagebox.showerror(
                "Render failed",
                f"ffmpeg error (project unchanged):\n\n{err}\n\n"
                "Tip: clips with mixed codecs need re-encoding. "
                "Try adding '-c:v libx264 -c:a aac' flags.",
                parent=self)

    def _export_audio(self):
        ff = _ffmpeg()
        if not ff:
            messagebox.showinfo("ffmpeg required",
                                "Audio export needs ffmpeg on PATH.",
                                parent=self)
            return
        audio_clips = []
        for t in self.project["tracks"]:
            if t["kind"] == "audio" and not t.get("muted"):
                audio_clips.extend(c["path"] for c in t["clips"]
                                   if Path(c.get("path", "")).exists())
        if not audio_clips:
            messagebox.showinfo("No audio", "Add audio clips first.", parent=self)
            return
        out = filedialog.asksaveasfilename(
            parent=self, defaultextension=".mp3",
            filetypes=[("MP3 audio", "*.mp3"), ("WAV audio", "*.wav")])
        if not out:
            return
        try:
            subprocess.run([ff, "-y", "-i", audio_clips[0], out],
                           check=True, capture_output=True)
            self._status.set(f"Audio exported: {Path(out).name}")
        except subprocess.CalledProcessError:
            messagebox.showerror("Export failed",
                                 "Audio export failed.", parent=self)

    # ── file I/O ──────────────────────────────────────────────────────────────

    def _new(self):
        if messagebox.askyesno("New project",
                               "Discard current project?", parent=self):
            self.project = self._empty_project()
            self.selected_clip  = None
            self.selected_track = 0
            self._refresh_all()

    def _save(self):
        p = filedialog.asksaveasfilename(
            parent=self, defaultextension=".hvs",
            initialfile=re.sub(r"[^\w -]", "_",
                               self.project.get("title", "video")) + ".hvs",
            filetypes=[("Studio video project", "*.hvs"),
                        ("JSON", "*.json")])
        if p:
            Path(p).write_text(
                json.dumps(self.project, indent=2, ensure_ascii=False),
                encoding="utf-8")
            self._status.set(f"Saved: {Path(p).name}")

    def _open(self):
        p = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Studio video project", "*.hvs *.json"),
                        ("All files", "*.*")])
        if not p:
            return
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            if data.get("format") != VIDEO_FORMAT:
                raise ValueError("Not a Studio video project")
            self.project = data
            self.project.setdefault("markers", [])
            self.project.setdefault("captions", [])
            self.selected_clip  = None
            self.selected_track = 0
            self._refresh_all()
            self._status.set(f"Opened: {Path(p).name}")
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc), parent=self)


# ── module-level import needed only here ──────────────────────────────────────
import re


def new_id():
    from uuid import uuid4
    return str(uuid4())


# ══════════════════════════════════════════════════════════════════════════════
#  ANIMATION STUDIO
# ══════════════════════════════════════════════════════════════════════════════

class AnimationStudio(tk.Toplevel):
    """
    Full-featured 2D frame-by-frame animation studio.

    Features
    ─────────
    • Multi-layer support with visibility, lock, opacity controls
    • Tools: Brush, Pencil, Line, Rectangle, Ellipse, Fill, Text, Eraser, Select
    • Adjustable brush size, opacity, smoothing
    • Onion skinning (prev/next frames, configurable frames and opacity)
    • Frame management: add, duplicate, delete, reorder, clear
    • FPS control and real-time canvas playback
    • Export: Animated GIF (Pillow), MP4 (ffmpeg), PNG frame sequence
    • Project save / open  (.has)
    • Undo / redo per frame
    • Color palette and custom color picker
    • Background color / image per layer
    • Rulers and grid overlay
    • Zoom in / out on the canvas
    """

    _TOOLS = ["Select", "Brush", "Pencil", "Line", "Rectangle",
              "Ellipse", "Fill", "Text", "Eraser"]

    _PALETTE = [
        "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF",
        "#FFFF00", "#FF00FF", "#00FFFF", "#FF8800", "#8800FF",
        "#315C8A", "#F4B544", "#547A5D", "#7B5AA6", "#C0392B",
        "#E74C3C", "#3498DB", "#2ECC71", "#F39C12", "#9B59B6",
    ]

    # ── project skeleton ──────────────────────────────────────────────────────

    def _empty_project(self) -> dict:
        return {
            "format": ANIM_FORMAT, "version": 2,
            "title": "Untitled Animation",
            "width": 960, "height": 540, "fps": 12,
            "total_frames": 24,
            "background": "#FFFFFF",
            "layers": [
                {"id": "bg",  "name": "Background", "visible": True,
                 "locked": False, "opacity": 1.0, "frames": {}},
                {"id": "drw", "name": "Drawing",    "visible": True,
                 "locked": False, "opacity": 1.0, "frames": {}},
                {"id": "fg",  "name": "Foreground", "visible": True,
                 "locked": False, "opacity": 1.0, "frames": {}},
            ],
        }

    # ── init ──────────────────────────────────────────────────────────────────

    def __init__(self, master):
        super().__init__(master)
        self.title("2D Animation Studio")
        self.geometry("1360x820")
        self.minsize(980, 640)

        self.project = self._empty_project()
        self.frame_index = 0
        self.active_layer = 1          # index into project["layers"]

        self.tool     = tk.StringVar(value="Brush")
        self.color    = "#315C8A"
        self.bg_color = "#FFFFFF"
        self.brush_size = tk.IntVar(value=5)
        self.brush_opacity = tk.DoubleVar(value=1.0)
        self.smooth   = tk.BooleanVar(value=True)

        self.onion_prev  = tk.IntVar(value=1)
        self.onion_next  = tk.IntVar(value=0)
        self.onion_opac  = tk.DoubleVar(value=0.35)

        self.show_grid   = tk.BooleanVar(value=False)
        self.show_rulers = tk.BooleanVar(value=True)
        self.zoom_level  = 1.0

        self._start_pt   = None
        self._cur_pts: list = []
        self._undo_stack: list = []   # list of serialized frame states
        self._redo_stack: list = []
        self._playing    = False
        self._prev_img   = None       # Pillow/Tk image reference

        self._build()
        self._refresh_all()
        self._bind_keys()

    # ── keyboard ──────────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.bind("<Control-z>",    lambda e: self._undo())
        self.bind("<Control-y>",    lambda e: self._redo())
        self.bind("<Control-s>",    lambda e: self._save())
        self.bind("<space>",        lambda e: self._play_toggle())
        self.bind("<Left>",         lambda e: self._go_frame(-1))
        self.bind("<Right>",        lambda e: self._go_frame(1))
        self.bind("<Control-d>",    lambda e: self._duplicate_frame())
        self.bind("<Delete>",       lambda e: self._delete_frame())
        # tool shortcuts
        for key, tool in [("b","Brush"),("e","Eraser"),
                          ("l","Line"),("r","Rectangle"),
                          ("o","Ellipse"),("t","Text"),
                          ("f","Fill"),("s","Select")]:
            self.bind(key, lambda e, t=tool: self.tool.set(t))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── toolbar ───────────────────────────────────────────────────────────
        tb = ttk.Frame(self)
        tb.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(tb, text="ANIMATION STUDIO",
                  font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 12))
        for label, cmd in [
            ("New",            self._new),
            ("Open…",          self._open),
            ("Save",           self._save),
            ("Canvas size",    self._canvas_size),
            ("Export GIF",     self._export_gif),
            ("Export PNG seq", self._export_png_seq),
            ("Export MP4",     self._export_mp4),
        ]:
            ttk.Button(tb, text=label, command=cmd).pack(side="right", padx=2)

        # ── body ──────────────────────────────────────────────────────────────
        pw = ttk.Panedwindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=8, pady=6)

        tools_col   = ttk.Frame(pw, width=180)
        center_col  = ttk.Frame(pw)
        timeline_col = ttk.Frame(pw, width=240)
        pw.add(tools_col,    weight=0)
        pw.add(center_col,   weight=1)
        pw.add(timeline_col, weight=0)

        self._build_tools(tools_col)
        self._build_canvas_area(center_col)
        self._build_timeline(timeline_col)

        # ── status ────────────────────────────────────────────────────────────
        sb = ttk.Frame(self)
        sb.pack(fill="x", padx=8, pady=(0, 6))
        self._status = tk.StringVar(value="Frame 1")
        ttk.Label(sb, textvariable=self._status).pack(side="left")
        ttk.Label(sb,
                  text="Space=play  ←/→=frame  Ctrl+Z=undo  "
                       "B=brush E=eraser L=line R=rect O=ellipse T=text",
                  foreground="#94a3b8").pack(side="right")

    def _build_tools(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        tools_tab  = ttk.Frame(nb)
        layers_tab = ttk.Frame(nb)
        nb.add(tools_tab,  text="Tools")
        nb.add(layers_tab, text="Layers")

        # Tools tab ────────────────────────────────────────────────────────────
        ttk.Label(tools_tab, text="Drawing tool",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6, pady=(6, 2))
        for t in self._TOOLS:
            ttk.Radiobutton(tools_tab, text=t, value=t,
                            variable=self.tool).pack(anchor="w", padx=10, pady=1)

        ttk.Separator(tools_tab).pack(fill="x", padx=6, pady=6)
        ttk.Label(tools_tab, text="Brush size").pack(anchor="w", padx=6)
        ttk.Spinbox(tools_tab, from_=1, to=120, textvariable=self.brush_size,
                    width=6).pack(anchor="w", padx=6, pady=(0, 4))
        ttk.Label(tools_tab, text="Opacity").pack(anchor="w", padx=6)
        ttk.Spinbox(tools_tab, from_=0.05, to=1.0, increment=0.05,
                    textvariable=self.brush_opacity,
                    width=6).pack(anchor="w", padx=6, pady=(0, 4))
        ttk.Checkbutton(tools_tab, text="Smooth strokes",
                        variable=self.smooth).pack(anchor="w", padx=6)

        ttk.Separator(tools_tab).pack(fill="x", padx=6, pady=6)
        ttk.Label(tools_tab, text="Foreground color").pack(anchor="w", padx=6)
        self._fg_swatch = tk.Label(tools_tab, bg=self.color,
                                   width=10, height=2, relief="solid",
                                   cursor="hand2")
        self._fg_swatch.pack(anchor="w", padx=6, pady=(0, 4))
        self._fg_swatch.bind("<Button-1>", lambda e: self._pick_color())

        ttk.Label(tools_tab, text="Background color").pack(anchor="w", padx=6)
        self._bg_swatch = tk.Label(tools_tab, bg=self.project["background"],
                                   width=10, height=2, relief="solid",
                                   cursor="hand2")
        self._bg_swatch.pack(anchor="w", padx=6, pady=(0, 4))
        self._bg_swatch.bind("<Button-1>", lambda e: self._pick_bg())

        ttk.Separator(tools_tab).pack(fill="x", padx=6, pady=6)
        ttk.Label(tools_tab, text="Quick palette").pack(anchor="w", padx=6)
        palette_frame = ttk.Frame(tools_tab)
        palette_frame.pack(anchor="w", padx=6, pady=(0, 4))
        for i, c in enumerate(self._PALETTE):
            btn = tk.Label(palette_frame, bg=c, width=2, height=1,
                           relief="raised", cursor="hand2")
            btn.grid(row=i // 5, column=i % 5, padx=1, pady=1)
            btn.bind("<Button-1>",
                     lambda e, col=c: self._set_color(col))

        ttk.Separator(tools_tab).pack(fill="x", padx=6, pady=6)
        ttk.Label(tools_tab, text="Onion skin",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=6)
        for label, var in [("Prev frames", self.onion_prev),
                           ("Next frames", self.onion_next)]:
            ttk.Label(tools_tab, text=label).pack(anchor="w", padx=6)
            ttk.Spinbox(tools_tab, from_=0, to=5, textvariable=var,
                        width=4,
                        command=self._redraw).pack(anchor="w", padx=6, pady=(0, 2))
        ttk.Label(tools_tab, text="Onion opacity").pack(anchor="w", padx=6)
        ttk.Spinbox(tools_tab, from_=0.05, to=0.9, increment=0.05,
                    textvariable=self.onion_opac, width=6,
                    command=self._redraw).pack(anchor="w", padx=6, pady=(0, 4))

        ttk.Separator(tools_tab).pack(fill="x", padx=6, pady=6)
        ttk.Label(tools_tab, text="View").pack(anchor="w", padx=6)
        ttk.Checkbutton(tools_tab, text="Show grid",
                        variable=self.show_grid,
                        command=self._redraw).pack(anchor="w", padx=6)
        ttk.Checkbutton(tools_tab, text="Show rulers",
                        variable=self.show_rulers,
                        command=self._redraw).pack(anchor="w", padx=6)
        z_row = ttk.Frame(tools_tab)
        z_row.pack(anchor="w", padx=6, pady=(4, 0))
        ttk.Button(z_row, text="−", width=2,
                   command=lambda: self._zoom(-0.25)).pack(side="left")
        self._zoom_label = ttk.Label(z_row, text="100%", width=6)
        self._zoom_label.pack(side="left")
        ttk.Button(z_row, text="+", width=2,
                   command=lambda: self._zoom(0.25)).pack(side="left")

        # Layers tab ───────────────────────────────────────────────────────────
        ttk.Label(layers_tab, text="Layers",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6, pady=(6, 2))
        self._layer_list = tk.Listbox(layers_tab, exportselection=False,
                                      activestyle="none")
        self._layer_list.pack(fill="both", expand=True, padx=6)
        self._layer_list.bind("<<ListboxSelect>>", self._on_layer_select)

        btns = ttk.Frame(layers_tab)
        btns.pack(fill="x", padx=6, pady=4)
        for t, c in [("Add",    self._add_layer),
                      ("Dup",    self._duplicate_layer),
                      ("Del",    self._delete_layer),
                      ("↑",      lambda: self._move_layer(-1)),
                      ("↓",      lambda: self._move_layer(1))]:
            ttk.Button(btns, text=t, command=c).pack(side="left", padx=1)

        layer_props = ttk.Frame(layers_tab)
        layer_props.pack(fill="x", padx=6)
        ttk.Label(layer_props, text="Opacity").pack(side="left")
        self._layer_opac = tk.DoubleVar(value=1.0)
        ttk.Spinbox(layer_props, from_=0.0, to=1.0, increment=0.05,
                    textvariable=self._layer_opac, width=6).pack(side="left")
        ttk.Button(layer_props, text="Apply",
                   command=self._apply_layer_opacity).pack(side="left", padx=4)

        toggle_frame = ttk.Frame(layers_tab)
        toggle_frame.pack(fill="x", padx=6, pady=2)
        ttk.Button(toggle_frame, text="Visible",
                   command=self._toggle_layer_visible).pack(side="left", padx=1)
        ttk.Button(toggle_frame, text="Lock",
                   command=self._toggle_layer_lock).pack(side="left", padx=1)

    def _build_canvas_area(self, parent):
        # Scrollable canvas wrapper
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg="#808080",
                                 highlightthickness=0)
        sb_h = ttk.Scrollbar(outer, orient="horizontal",
                              command=self._canvas.xview)
        sb_v = ttk.Scrollbar(outer, orient="vertical",
                              command=self._canvas.yview)
        self._canvas.configure(xscrollcommand=sb_h.set,
                               yscrollcommand=sb_v.set)
        sb_h.pack(side="bottom", fill="x")
        sb_v.pack(side="right",  fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._canvas.bind("<ButtonPress-1>",   self._down)
        self._canvas.bind("<B1-Motion>",       self._drag)
        self._canvas.bind("<ButtonRelease-1>", self._up)
        self._canvas.bind("<Configure>",
                          lambda e: self._redraw())

        # Transport row under canvas
        tr = ttk.Frame(parent)
        tr.pack(fill="x", padx=4, pady=4)
        ttk.Button(tr, text="|◀", width=3,
                   command=lambda: self._go_frame(-self.frame_index)).pack(
            side="left")
        ttk.Button(tr, text="◀", width=3,
                   command=lambda: self._go_frame(-1)).pack(side="left")
        self._play_btn = ttk.Button(tr, text="▶ Play",
                                    command=self._play_toggle)
        self._play_btn.pack(side="left", padx=4)
        ttk.Button(tr, text="▶|", width=3,
                   command=lambda: self._go_frame(1)).pack(side="left")

        ttk.Label(tr, text="FPS").pack(side="left", padx=(12, 2))
        self._fps_var = tk.IntVar(value=self.project["fps"])
        ttk.Spinbox(tr, from_=1, to=60, textvariable=self._fps_var,
                    width=4,
                    command=lambda: self._set_fps()).pack(side="left")

        ttk.Button(tr, text="Add frame",
                   command=self._add_frame).pack(side="left", padx=8)
        ttk.Button(tr, text="Duplicate frame",
                   command=self._duplicate_frame).pack(side="left", padx=2)
        ttk.Button(tr, text="Clear frame",
                   command=self._clear_frame).pack(side="left", padx=2)
        ttk.Button(tr, text="Undo",
                   command=self._undo).pack(side="left", padx=8)
        ttk.Button(tr, text="Redo",
                   command=self._redo).pack(side="left", padx=2)

        # Frame scrubber
        scr_frame = ttk.Frame(parent)
        scr_frame.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Label(scr_frame, text="Frame:").pack(side="left")
        self._frame_scale = tk.Scale(
            scr_frame, from_=0,
            to=max(0, self.project["total_frames"] - 1),
            orient="horizontal", resolution=1,
            command=self._scrub_frame,
            bg=self.cget("bg"), highlightthickness=0)
        self._frame_scale.pack(side="left", fill="x", expand=True)
        self._frame_label = ttk.Label(scr_frame, text="1 / 24")
        self._frame_label.pack(side="left", padx=4)

    def _build_timeline(self, parent):
        ttk.Label(parent, text="Frames",
                  font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=6, pady=(6, 2))
        self._frame_list = tk.Listbox(parent, exportselection=False,
                                      activestyle="none")
        self._frame_list.pack(fill="both", expand=True, padx=6)
        self._frame_list.bind("<<ListboxSelect>>", self._on_frame_select)

        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=6, pady=4)
        for t, c in [("Add",   self._add_frame),
                      ("Dup",   self._duplicate_frame),
                      ("Del",   self._delete_frame),
                      ("↑",     lambda: self._move_frame(-1)),
                      ("↓",     lambda: self._move_frame(1)),
                      ("Clear", self._clear_frame)]:
            ttk.Button(btns, text=t, command=c).pack(side="left", padx=1)

    # ── refresh helpers ───────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_layer_list()
        self._refresh_frame_list()
        self._redraw()

    def _refresh_layer_list(self):
        self._layer_list.delete(0, "end")
        for i, layer in enumerate(self.project["layers"]):
            eye  = "👁" if layer["visible"] else "◻"
            lock = "🔒" if layer.get("locked") else "  "
            mark = " ←" if i == self.active_layer else ""
            self._layer_list.insert(
                "end", f"{eye}{lock} {layer['name']}{mark}")
        self._layer_list.selection_set(self.active_layer)

    def _refresh_frame_list(self):
        total = self.project["total_frames"]
        self._frame_list.delete(0, "end")
        for i in range(total):
            ops_count = 0
            for layer in self.project["layers"]:
                ops = layer["frames"].get(str(i), [])
                ops_count += len(ops)
            mark = " ◀" if i == self.frame_index else ""
            self._frame_list.insert(
                "end", f"Frame {i+1:03d}  ·  {ops_count} ops{mark}")
        if self.frame_index < self._frame_list.size():
            self._frame_list.selection_set(self.frame_index)
        # update scrubber
        self._frame_scale.configure(to=max(0, total - 1))
        self._frame_scale.set(self.frame_index)
        self._frame_label.configure(
            text=f"{self.frame_index + 1} / {total}")
        self._status.set(
            f"Frame {self.frame_index + 1} / {total}  •  "
            f"{self.project['fps']} fps  •  "
            f"Tool: {self.tool.get()}  •  "
            f"Layer: {self.project['layers'][self.active_layer]['name']}")

    # ── drawing ───────────────────────────────────────────────────────────────

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        cw = max(200, c.winfo_width())
        ch = max(100, c.winfo_height())
        pw = int(self.project["width"]  * self.zoom_level)
        ph = int(self.project["height"] * self.zoom_level)
        ox = max(0, (cw - pw) // 2)
        oy = max(0, (ch - ph) // 2)
        # paper
        c.create_rectangle(ox, oy, ox + pw, oy + ph,
                           fill=self.project["background"], outline="#aaa")
        # rulers
        if self.show_rulers.get():
            for x in range(0, pw, 50):
                c.create_line(ox + x, oy, ox + x, oy + 8,
                              fill="#666")
                c.create_text(ox + x + 2, oy + 1, text=str(int(x / self.zoom_level)),
                              anchor="nw", fill="#666",
                              font=("Segoe UI", 6))
        # grid
        if self.show_grid.get():
            gs = max(8, int(20 * self.zoom_level))
            for x in range(0, pw, gs):
                c.create_line(ox + x, oy, ox + x, oy + ph,
                              fill="#ddd", dash=(2, 4))
            for y in range(0, ph, gs):
                c.create_line(ox, oy + y, ox + pw, oy + y,
                              fill="#ddd", dash=(2, 4))
        # onion skin — previous frames
        for back in range(self.onion_prev.get(), 0, -1):
            fi = self.frame_index - back
            if fi >= 0:
                opacity = self.onion_opac.get() * (1 - back / (self.onion_prev.get() + 1))
                self._paint_frame_ops(c, fi, ox, oy, opacity,
                                      ghost_color="#3366cc")
        # onion skin — next frames
        for fwd in range(1, self.onion_next.get() + 1):
            fi = self.frame_index + fwd
            if fi < self.project["total_frames"]:
                opacity = self.onion_opac.get() * (1 - fwd / (self.onion_next.get() + 1))
                self._paint_frame_ops(c, fi, ox, oy, opacity,
                                      ghost_color="#cc3333")
        # layers in order
        for layer in self.project["layers"]:
            if layer["visible"]:
                self._paint_frame_ops(c, self.frame_index,
                                      ox, oy, layer["opacity"],
                                      layer_id=layer["id"])

        c.configure(scrollregion=(0, 0, max(cw, ox + pw + 40),
                                  max(ch, oy + ph + 40)))
        self._refresh_frame_list()

    def _paint_frame_ops(self, canvas, frame_idx: int,
                         ox: int, oy: int,
                         global_opacity: float = 1.0,
                         ghost_color: Optional[str] = None,
                         layer_id: Optional[str] = None):
        """Paint ops from all layers (or a specific layer) at frame_idx."""
        layers = self.project["layers"]
        if layer_id is not None:
            layers = [l for l in layers if l["id"] == layer_id]
        z = self.zoom_level
        for layer in layers:
            if not layer.get("visible", True):
                continue
            ops = layer["frames"].get(str(frame_idx), [])
            for op in ops:
                pts = [(ox + int(x * z), oy + int(y * z))
                       for x, y in op.get("pts", [])]
                if not pts:
                    continue
                t     = op.get("tool", "Brush")
                color = ghost_color if ghost_color else op.get("color", "#000")
                width = max(1, int(op.get("width", 3) * z))
                flat  = [coord for pt in pts for coord in pt]
                if t in ("Brush", "Pencil"):
                    if len(pts) >= 2:
                        canvas.create_line(*flat, fill=color, width=width,
                                           smooth=op.get("smooth", True),
                                           capstyle="round",
                                           joinstyle="round")
                    elif len(pts) == 1:
                        r = max(1, width // 2)
                        x, y = pts[0]
                        canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=color, outline="")
                elif t == "Line":
                    if len(pts) >= 2:
                        canvas.create_line(*pts[0], *pts[-1],
                                           fill=color, width=width)
                elif t == "Rectangle":
                    if len(pts) >= 2:
                        fc = op.get("fill_color", "")
                        canvas.create_rectangle(*pts[0], *pts[-1],
                                               outline=color, width=width,
                                               fill=fc if fc else "")
                elif t == "Ellipse":
                    if len(pts) >= 2:
                        fc = op.get("fill_color", "")
                        canvas.create_oval(*pts[0], *pts[-1],
                                           outline=color, width=width,
                                           fill=fc if fc else "")
                elif t == "Fill":
                    if pts:
                        r = max(60, int(80 * z))
                        canvas.create_oval(pts[0][0] - r,
                                           pts[0][1] - r,
                                           pts[0][0] + r,
                                           pts[0][1] + r,
                                           fill=color, outline="")
                elif t == "Text":
                    if pts:
                        sz = max(10, int(op.get("width", 3) * 4 * z))
                        canvas.create_text(*pts[0],
                                           text=op.get("text", ""),
                                           fill=color,
                                           font=("Segoe UI", sz),
                                           anchor="nw")

    # ── input events ──────────────────────────────────────────────────────────

    def _canvas_to_proj(self, ex: int, ey: int) -> tuple:
        cw = max(200, self._canvas.winfo_width())
        ch = max(100, self._canvas.winfo_height())
        pw = int(self.project["width"]  * self.zoom_level)
        ph = int(self.project["height"] * self.zoom_level)
        ox = max(0, (cw - pw) // 2)
        oy = max(0, (ch - ph) // 2)
        x = (ex - ox) / self.zoom_level
        y = (ey - oy) / self.zoom_level
        return x, y

    def _down(self, e):
        layer = self._current_layer()
        if layer is None or layer.get("locked"):
            return
        if self.tool.get() == "Select":
            return
        if self.tool.get() == "Text":
            text = simpledialog.askstring("Text", "Enter text:", parent=self)
            if text:
                pt = self._canvas_to_proj(e.x, e.y)
                op = {"tool": "Text", "pts": [pt],
                      "color": self.color, "width": self.brush_size.get(),
                      "text": text, "smooth": False}
                self._push_undo()
                self._get_ops().append(op)
                self._redraw()
            return
        if self.tool.get() == "Fill":
            pt = self._canvas_to_proj(e.x, e.y)
            op = {"tool": "Fill", "pts": [pt],
                  "color": self.color, "width": self.brush_size.get(),
                  "smooth": False}
            self._push_undo()
            self._get_ops().append(op)
            self._redraw()
            return
        self._push_undo()
        self._start_pt = self._canvas_to_proj(e.x, e.y)
        self._cur_pts  = [self._start_pt]

    def _drag(self, e):
        if self._start_pt is None:
            return
        pt = self._canvas_to_proj(e.x, e.y)
        self._cur_pts.append(pt)
        t = self.tool.get()
        if t in ("Brush", "Pencil", "Eraser"):
            # live stroke preview
            self._redraw()
            z = self.zoom_level
            cw = max(200, self._canvas.winfo_width())
            ch = max(100, self._canvas.winfo_height())
            pw = int(self.project["width"]  * z)
            ph = int(self.project["height"] * z)
            ox = max(0, (cw - pw) // 2)
            oy = max(0, (ch - ph) // 2)
            screen_pts = [(ox + int(x * z), oy + int(y * z))
                          for x, y in self._cur_pts]
            flat = [c for p in screen_pts for c in p]
            if len(screen_pts) >= 2:
                color = self.project["background"] if t == "Eraser" else self.color
                self._canvas.create_line(*flat, fill=color,
                                         width=max(1, int(self.brush_size.get() * z)),
                                         smooth=self.smooth.get(),
                                         capstyle="round", tags="_preview")
        else:
            self._redraw()

    def _up(self, e):
        if self._start_pt is None:
            return
        pt  = self._canvas_to_proj(e.x, e.y)
        t   = self.tool.get()
        if t == "Eraser":
            # Remove the last op on this layer
            ops = self._get_ops()
            if ops:
                ops.pop()
        elif t not in ("Select", "Text", "Fill"):
            if t in ("Brush", "Pencil"):
                pts = self._cur_pts
            else:
                pts = [self._start_pt, pt]
            op = {
                "tool":   t,
                "pts":    pts,
                "color":  self.color,
                "width":  self.brush_size.get(),
                "smooth": self.smooth.get(),
                "opacity": self.brush_opacity.get(),
                "fill_color": "",
            }
            self._get_ops().append(op)
        self._start_pt = None
        self._cur_pts  = []
        self._redraw()

    # ── layer helpers ─────────────────────────────────────────────────────────

    def _current_layer(self) -> Optional[dict]:
        layers = self.project["layers"]
        if 0 <= self.active_layer < len(layers):
            return layers[self.active_layer]
        return None

    def _get_ops(self) -> list:
        layer = self._current_layer()
        if layer is None:
            return []
        key = str(self.frame_index)
        if key not in layer["frames"]:
            layer["frames"][key] = []
        return layer["frames"][key]

    def _on_layer_select(self, _e=None):
        s = self._layer_list.curselection()
        if s:
            self.active_layer = s[0]
            self._layer_opac.set(
                self.project["layers"][self.active_layer].get("opacity", 1.0))
            self._refresh_layer_list()

    def _add_layer(self):
        name = simpledialog.askstring("New layer", "Layer name:",
                                      parent=self) or f"Layer {len(self.project['layers'])+1}"
        layer = {"id": new_id(), "name": name,
                 "visible": True, "locked": False,
                 "opacity": 1.0, "frames": {}}
        self.project["layers"].insert(self.active_layer + 1, layer)
        self.active_layer += 1
        self._refresh_layer_list()

    def _duplicate_layer(self):
        layer = self._current_layer()
        if layer is None:
            return
        new_layer = copy.deepcopy(layer)
        new_layer["id"]   = new_id()
        new_layer["name"] = layer["name"] + " copy"
        self.project["layers"].insert(self.active_layer + 1, new_layer)
        self.active_layer += 1
        self._refresh_layer_list()

    def _delete_layer(self):
        if len(self.project["layers"]) <= 1:
            messagebox.showinfo("Cannot delete",
                                "A project needs at least one layer.",
                                parent=self)
            return
        self.project["layers"].pop(self.active_layer)
        self.active_layer = max(0, self.active_layer - 1)
        self._refresh_layer_list()
        self._redraw()

    def _move_layer(self, d: int):
        n = self.active_layer + d
        layers = self.project["layers"]
        if 0 <= n < len(layers):
            layers[self.active_layer], layers[n] = layers[n], layers[self.active_layer]
            self.active_layer = n
            self._refresh_layer_list()
            self._redraw()

    def _toggle_layer_visible(self):
        layer = self._current_layer()
        if layer:
            layer["visible"] = not layer.get("visible", True)
            self._refresh_layer_list()
            self._redraw()

    def _toggle_layer_lock(self):
        layer = self._current_layer()
        if layer:
            layer["locked"] = not layer.get("locked", False)
            self._refresh_layer_list()

    def _apply_layer_opacity(self):
        layer = self._current_layer()
        if layer:
            layer["opacity"] = max(0.0, min(1.0, self._layer_opac.get()))
            self._redraw()

    # ── frame helpers ─────────────────────────────────────────────────────────

    def _go_frame(self, d: int):
        total = self.project["total_frames"]
        self.frame_index = max(0, min(total - 1, self.frame_index + d))
        self._redraw()

    def _scrub_frame(self, val):
        self.frame_index = int(float(val))
        self._redraw()

    def _on_frame_select(self, _e=None):
        s = self._frame_list.curselection()
        if s:
            self.frame_index = s[0]
            self._redraw()

    def _add_frame(self):
        self.project["total_frames"] += 1
        self.frame_index = self.project["total_frames"] - 1
        self._frame_scale.configure(to=self.project["total_frames"] - 1)
        self._redraw()

    def _duplicate_frame(self):
        fi = self.frame_index
        for layer in self.project["layers"]:
            src = copy.deepcopy(layer["frames"].get(str(fi), []))
            # shift all frames after fi
            new_frames = {}
            for k, v in layer["frames"].items():
                idx = int(k)
                if idx > fi:
                    new_frames[str(idx + 1)] = v
                else:
                    new_frames[k] = v
            new_frames[str(fi + 1)] = src
            layer["frames"] = new_frames
        self.project["total_frames"] += 1
        self.frame_index = fi + 1
        self._frame_scale.configure(to=self.project["total_frames"] - 1)
        self._redraw()

    def _delete_frame(self):
        total = self.project["total_frames"]
        if total <= 1:
            messagebox.showinfo("Cannot delete",
                                "A project needs at least one frame.",
                                parent=self)
            return
        fi = self.frame_index
        for layer in self.project["layers"]:
            new_frames = {}
            for k, v in layer["frames"].items():
                idx = int(k)
                if idx < fi:
                    new_frames[k] = v
                elif idx > fi:
                    new_frames[str(idx - 1)] = v
                # idx == fi is dropped
            layer["frames"] = new_frames
        self.project["total_frames"] -= 1
        self.frame_index = max(0, fi - 1)
        self._frame_scale.configure(to=max(0, self.project["total_frames"] - 1))
        self._redraw()

    def _move_frame(self, d: int):
        fi  = self.frame_index
        fj  = fi + d
        total = self.project["total_frames"]
        if not (0 <= fj < total):
            return
        for layer in self.project["layers"]:
            a = copy.deepcopy(layer["frames"].get(str(fi), []))
            b = copy.deepcopy(layer["frames"].get(str(fj), []))
            layer["frames"][str(fi)] = b
            layer["frames"][str(fj)] = a
        self.frame_index = fj
        self._redraw()

    def _clear_frame(self):
        for layer in self.project["layers"]:
            layer["frames"].pop(str(self.frame_index), None)
        self._redraw()

    def _set_fps(self):
        self.project["fps"] = max(1, min(60, self._fps_var.get()))
        self._refresh_frame_list()

    # ── undo / redo ───────────────────────────────────────────────────────────

    def _push_undo(self):
        snapshot = json.dumps(
            [{"id": l["id"],
              "frame": l["frames"].get(str(self.frame_index), [])}
             for l in self.project["layers"]])
        self._undo_stack.append(snapshot)
        self._undo_stack = self._undo_stack[-60:]
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack:
            return
        # save current state to redo
        current = json.dumps(
            [{"id": l["id"],
              "frame": l["frames"].get(str(self.frame_index), [])}
             for l in self.project["layers"]])
        self._redo_stack.append(current)
        state = json.loads(self._undo_stack.pop())
        for item in state:
            layer = next(
                (l for l in self.project["layers"] if l["id"] == item["id"]),
                None)
            if layer is not None:
                layer["frames"][str(self.frame_index)] = item["frame"]
        self._redraw()

    def _redo(self):
        if not self._redo_stack:
            return
        current = json.dumps(
            [{"id": l["id"],
              "frame": l["frames"].get(str(self.frame_index), [])}
             for l in self.project["layers"]])
        self._undo_stack.append(current)
        state = json.loads(self._redo_stack.pop())
        for item in state:
            layer = next(
                (l for l in self.project["layers"] if l["id"] == item["id"]),
                None)
            if layer is not None:
                layer["frames"][str(self.frame_index)] = item["frame"]
        self._redraw()

    # ── color ─────────────────────────────────────────────────────────────────

    def _pick_color(self):
        c = colorchooser.askcolor(self.color, parent=self)[1]
        if c:
            self._set_color(c)

    def _set_color(self, c: str):
        self.color = c
        self._fg_swatch.configure(bg=c)

    def _pick_bg(self):
        c = colorchooser.askcolor(
            self.project.get("background", "#FFFFFF"), parent=self)[1]
        if c:
            self.project["background"] = c
            self.bg_color = c
            self._bg_swatch.configure(bg=c)
            self._redraw()

    # ── zoom ──────────────────────────────────────────────────────────────────

    def _zoom(self, delta: float):
        self.zoom_level = max(0.25, min(4.0, self.zoom_level + delta))
        self._zoom_label.configure(text=f"{int(self.zoom_level * 100)}%")
        self._redraw()

    # ── playback ──────────────────────────────────────────────────────────────

    def _play_toggle(self):
        self._playing = not self._playing
        self._play_btn.configure(
            text="⏸ Pause" if self._playing else "▶ Play")
        if self._playing:
            self._tick()

    def _tick(self):
        if not self._playing:
            return
        total = self.project["total_frames"]
        self.frame_index = (self.frame_index + 1) % total
        self._redraw()
        delay = max(16, int(1000 / self.project["fps"]))
        self.after(delay, self._tick)

    # ── canvas size ───────────────────────────────────────────────────────────

    def _canvas_size(self):
        win = tk.Toplevel(self)
        win.title("Canvas size")
        win.transient(self)
        w_var = tk.IntVar(value=self.project["width"])
        h_var = tk.IntVar(value=self.project["height"])
        ttk.Label(win, text="Width").grid(row=0, column=0, padx=12, pady=6)
        ttk.Spinbox(win, from_=64, to=7680, textvariable=w_var,
                    width=8).grid(row=0, column=1, padx=12, pady=6)
        ttk.Label(win, text="Height").grid(row=1, column=0, padx=12, pady=6)
        ttk.Spinbox(win, from_=64, to=4320, textvariable=h_var,
                    width=8).grid(row=1, column=1, padx=12, pady=6)
        presets = [("HD 1280×720", 1280, 720),
                   ("Full HD 1920×1080", 1920, 1080),
                   ("4K 3840×2160", 3840, 2160),
                   ("Square 1080×1080", 1080, 1080),
                   ("Story 1080×1920", 1080, 1920),
                   ("Classic 960×540", 960, 540)]
        for row, (label, pw, ph) in enumerate(presets, 2):
            ttk.Button(win, text=label,
                       command=lambda w=pw, h=ph: (
                           w_var.set(w), h_var.set(h))).grid(
                row=row, column=0, columnspan=2,
                padx=12, pady=2, sticky="ew")

        def apply():
            self.project["width"]  = w_var.get()
            self.project["height"] = h_var.get()
            win.destroy()
            self._redraw()

        ttk.Button(win, text="Apply", command=apply).grid(
            row=row + 1, column=0, columnspan=2,
            padx=12, pady=(8, 14), sticky="ew")

    # ── render helpers ────────────────────────────────────────────────────────

    def _render_frame_image(self, frame_idx: int):
        """Render all visible layers at frame_idx to a Pillow Image."""
        from PIL import Image, ImageDraw as PilDraw, ImageFont
        pw = self.project["width"]
        ph = self.project["height"]
        bg = self.project.get("background", "#FFFFFF")
        im = Image.new("RGBA", (pw, ph), bg)
        d  = PilDraw.Draw(im)
        for layer in self.project["layers"]:
            if not layer.get("visible", True):
                continue
            ops = layer["frames"].get(str(frame_idx), [])
            for op in ops:
                pts  = [(int(x), int(y)) for x, y in op.get("pts", [])]
                t    = op.get("tool", "Brush")
                col  = op.get("color", "#000")
                w    = max(1, op.get("width", 3))
                if not pts:
                    continue
                if t in ("Brush", "Pencil"):
                    if len(pts) >= 2:
                        d.line(pts, fill=col, width=w, joint="curve")
                    else:
                        r = max(1, w // 2)
                        x, y = pts[0]
                        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
                elif t == "Line" and len(pts) >= 2:
                    d.line([pts[0], pts[-1]], fill=col, width=w)
                elif t == "Rectangle" and len(pts) >= 2:
                    fc = op.get("fill_color", "")
                    d.rectangle([pts[0], pts[-1]],
                                 outline=col, width=w,
                                 fill=fc if fc else None)
                elif t == "Ellipse" and len(pts) >= 2:
                    fc = op.get("fill_color", "")
                    d.ellipse([pts[0], pts[-1]],
                               outline=col, width=w,
                               fill=fc if fc else None)
                elif t == "Fill" and pts:
                    r = 80
                    d.ellipse((pts[0][0] - r, pts[0][1] - r,
                               pts[0][0] + r, pts[0][1] + r), fill=col)
                elif t == "Text" and pts:
                    try:
                        fnt = ImageFont.truetype(
                            "C:/Windows/Fonts/segoeui.ttf",
                            max(12, w * 4))
                    except Exception:
                        fnt = ImageFont.load_default()
                    d.text(pts[0], op.get("text", ""),
                           fill=col, font=fnt)
        return im.convert("RGB")

    # ── export ────────────────────────────────────────────────────────────────

    def _export_gif(self):
        if not _pil_available():
            messagebox.showinfo(
                "Pillow needed",
                "Animated GIF export needs Pillow.\n"
                "Install: python -m pip install pillow",
                parent=self)
            return
        p = filedialog.asksaveasfilename(
            parent=self, defaultextension=".gif",
            filetypes=[("Animated GIF", "*.gif")])
        if not p:
            return
        try:
            total = self.project["total_frames"]
            frames = [self._render_frame_image(i) for i in range(total)]
            if not frames:
                return
            dur = max(20, int(1000 / self.project["fps"]))
            frames[0].save(p, save_all=True,
                           append_images=frames[1:],
                           loop=0, duration=dur,
                           optimize=False)
            self._status.set(f"GIF exported: {Path(p).name}")
            messagebox.showinfo("Exported",
                                f"Animated GIF saved:\n{p}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _export_png_seq(self):
        if not _pil_available():
            messagebox.showinfo(
                "Pillow needed",
                "PNG sequence export needs Pillow.\n"
                "Install: python -m pip install pillow",
                parent=self)
            return
        folder = filedialog.askdirectory(parent=self,
                                         title="Save PNG sequence folder")
        if not folder:
            return
        try:
            total = self.project["total_frames"]
            for i in range(total):
                im = self._render_frame_image(i)
                im.save(Path(folder) / f"frame_{i+1:04d}.png")
            self._status.set(f"PNG sequence saved in {folder}")
            messagebox.showinfo("Exported",
                                f"{total} PNG frames saved in:\n{folder}",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _export_mp4(self):
        ff = _ffmpeg()
        if not ff:
            messagebox.showinfo(
                "ffmpeg not found",
                "MP4 export needs ffmpeg.\n\n"
                "Either export as GIF (works now) or install ffmpeg:\n"
                "winget install ffmpeg",
                parent=self)
            return
        if not _pil_available():
            messagebox.showinfo(
                "Pillow needed",
                "MP4 export needs Pillow to render frames.\n"
                "Install: python -m pip install pillow",
                parent=self)
            return
        out = filedialog.asksaveasfilename(
            parent=self, defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")])
        if not out:
            return
        try:
            with tempfile.TemporaryDirectory() as tmp:
                total = self.project["total_frames"]
                for i in range(total):
                    im = self._render_frame_image(i)
                    im.save(Path(tmp) / f"frame_{i+1:04d}.png")
                subprocess.run([
                    ff, "-y",
                    "-framerate", str(self.project["fps"]),
                    "-i", str(Path(tmp) / "frame_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    out
                ], check=True, capture_output=True)
            self._status.set(f"MP4 exported: {Path(out).name}")
            messagebox.showinfo("Exported",
                                f"MP4 saved:\n{out}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    # ── file I/O ──────────────────────────────────────────────────────────────

    def _new(self):
        if messagebox.askyesno("New project",
                               "Discard current project?", parent=self):
            self.project     = self._empty_project()
            self.frame_index = 0
            self.active_layer = 1
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._refresh_all()

    def _save(self):
        import re as _re
        safe = _re.sub(r"[^\w -]", "_",
                       self.project.get("title", "animation"))
        p = filedialog.asksaveasfilename(
            parent=self, defaultextension=".has",
            initialfile=safe + ".has",
            filetypes=[("Studio animation project", "*.has"),
                        ("JSON", "*.json")])
        if p:
            Path(p).write_text(
                json.dumps(self.project, indent=2, ensure_ascii=False),
                encoding="utf-8")
            self._status.set(f"Saved: {Path(p).name}")

    def _open(self):
        p = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Studio animation project", "*.has *.json"),
                        ("All files", "*.*")])
        if not p:
            return
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            if data.get("format") != ANIM_FORMAT:
                raise ValueError("Not a Studio animation project")
            self.project     = data
            self.frame_index = 0
            self.active_layer = min(1, len(data["layers"]) - 1)
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._refresh_all()
            self._status.set(f"Opened: {Path(p).name}")
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc), parent=self)
