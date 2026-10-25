"""Shared, versioned project foundations for the three Studio departments.

These models are deliberately UI-independent so they can be tested without a
window, saved safely, and later rendered by richer engines.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from uuid import uuid4

def new_id() -> str:
    return str(uuid4())

# ─────────────────────────────────────────────────────────────
#  Design / Canva-style scene objects
# ─────────────────────────────────────────────────────────────

@dataclass
class SceneObject:
    kind: str                           # "text" | "image" | "shape" | "group" | "video"
    x: float = 0.0
    y: float = 0.0
    width: float = 200.0
    height: float = 100.0
    rotation: float = 0.0
    opacity: float = 1.0
    locked: bool = False
    visible: bool = True
    z_index: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)

    def move(self, dx: float, dy: float):
        self.x += dx; self.y += dy

    def resize(self, w: float, h: float):
        self.width = max(1.0, w); self.height = max(1.0, h)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SceneObject":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ScenePage:
    objects: List[SceneObject] = field(default_factory=list)
    background: str = "#FFFFFF"
    background_image: Optional[str] = None
    grid_enabled: bool = False
    grid_size: int = 20
    snap_to_grid: bool = False
    id: str = field(default_factory=new_id)

    def add(self, kind: str, **payload) -> SceneObject:
        obj = SceneObject(kind=kind, z_index=len(self.objects), payload=payload)
        self.objects.append(obj)
        return obj

    def remove(self, object_id: str):
        self.objects = [o for o in self.objects if o.id != object_id]

    def find(self, object_id: str) -> Optional[SceneObject]:
        return next((o for o in self.objects if o.id == object_id), None)

    def reorder(self, object_id: str, target_index: int):
        i = next((i for i, x in enumerate(self.objects) if x.id == object_id), None)
        if i is None:
            return
        item = self.objects.pop(i)
        self.objects.insert(max(0, min(target_index, len(self.objects))), item)
        for z, obj in enumerate(self.objects):
            obj.z_index = z

    def bring_forward(self, object_id: str):
        objs = self.objects
        i = next((i for i, o in enumerate(objs) if o.id == object_id), None)
        if i is not None and i < len(objs) - 1:
            objs[i], objs[i + 1] = objs[i + 1], objs[i]
            objs[i].z_index = i; objs[i + 1].z_index = i + 1

    def send_backward(self, object_id: str):
        objs = self.objects
        i = next((i for i, o in enumerate(objs) if o.id == object_id), None)
        if i is not None and i > 0:
            objs[i], objs[i - 1] = objs[i - 1], objs[i]
            objs[i].z_index = i; objs[i - 1].z_index = i - 1

    def to_dict(self) -> dict:
        return {
            "objects": [o.to_dict() for o in self.objects],
            "background": self.background,
            "background_image": self.background_image,
            "grid_enabled": self.grid_enabled,
            "grid_size": self.grid_size,
            "snap_to_grid": self.snap_to_grid,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScenePage":
        objs = [SceneObject.from_dict(o) for o in d.get("objects", [])]
        return cls(
            objects=objs,
            background=d.get("background", "#FFFFFF"),
            background_image=d.get("background_image"),
            grid_enabled=d.get("grid_enabled", False),
            grid_size=d.get("grid_size", 20),
            snap_to_grid=d.get("snap_to_grid", False),
            id=d.get("id", new_id()),
        )


# ─────────────────────────────────────────────────────────────
#  Video / Timeline models
# ─────────────────────────────────────────────────────────────

@dataclass
class TimelineClip:
    path: str
    start: float = 0.0
    end: Optional[float] = None
    offset: float = 0.0           # position on the timeline in seconds
    volume: float = 1.0
    opacity: float = 1.0
    speed: float = 1.0
    transition: str = "Cut"
    transition_duration: float = 0.5
    filters: List[str] = field(default_factory=list)
    color_grading: Dict[str, float] = field(default_factory=lambda: {
        "brightness": 0.0, "contrast": 0.0, "saturation": 0.0,
        "hue": 0.0, "temperature": 0.0
    })
    muted: bool = False
    label: str = ""
    id: str = field(default_factory=new_id)


@dataclass
class TimelineTrack:
    name: str
    kind: str          # "video" | "audio" | "title" | "effect" | "image"
    muted: bool = False
    locked: bool = False
    height: int = 48
    color: str = "#315C8A"
    clips: List[TimelineClip] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def add_clip(self, path: str, **kwargs) -> TimelineClip:
        clip = TimelineClip(path=path, **kwargs)
        self.clips.append(clip)
        return clip

    def remove_clip(self, clip_id: str):
        self.clips = [c for c in self.clips if c.id != clip_id]


@dataclass
class TimelineMarker:
    time: float
    label: str = ""
    color: str = "#F4B544"
    id: str = field(default_factory=new_id)


@dataclass
class TimelineProject:
    title: str = "Untitled Video"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    duration: float = 0.0
    tracks: List[TimelineTrack] = field(default_factory=lambda: [
        TimelineTrack("Video 1", "video", color="#315C8A"),
        TimelineTrack("Video 2", "video", color="#1D4E89"),
        TimelineTrack("Audio 1", "audio", color="#547A5D"),
        TimelineTrack("Audio 2", "audio", color="#2D6A4F"),
        TimelineTrack("Titles",  "title", color="#7B5AA6"),
        TimelineTrack("Effects", "effect", color="#C0392B"),
    ])
    markers: List[TimelineMarker] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_track(self, name: str, kind: str) -> TimelineTrack:
        t = TimelineTrack(name, kind)
        self.tracks.append(t)
        return t

    def track(self, kind: str) -> Optional[TimelineTrack]:
        return next((x for x in self.tracks if x.kind == kind), None)

    def tracks_of_kind(self, kind: str) -> List[TimelineTrack]:
        return [x for x in self.tracks if x.kind == kind]

    def add_marker(self, time: float, label: str = "") -> TimelineMarker:
        m = TimelineMarker(time=time, label=label)
        self.markers.append(m)
        return m

    def computed_duration(self) -> float:
        d = 0.0
        for t in self.tracks:
            for c in t.clips:
                end = (c.end or 0) + c.offset
                if end > d:
                    d = end
        return d


# ─────────────────────────────────────────────────────────────
#  Animation / 2D models
# ─────────────────────────────────────────────────────────────

@dataclass
class Keyframe:
    frame: int
    x: Optional[float] = None
    y: Optional[float] = None
    scale_x: Optional[float] = None
    scale_y: Optional[float] = None
    rotation: Optional[float] = None
    opacity: Optional[float] = None
    # Legacy alias
    scale: Optional[float] = None
    easing: str = "linear"   # "linear" | "ease-in" | "ease-out" | "ease-in-out"


def _ease(t: float, easing: str) -> float:
    if easing == "ease-in":
        return t * t
    elif easing == "ease-out":
        return t * (2 - t)
    elif easing == "ease-in-out":
        return t * t * (3 - 2 * t)
    return t  # linear


def interpolate(a: Keyframe, b: Keyframe, frame: int) -> dict:
    """Interpolate all properties between two keyframes at `frame`."""
    if b.frame == a.frame:
        return {k: getattr(a, k) for k in ("x", "y", "scale", "scale_x", "scale_y", "rotation", "opacity")}
    raw_t = (frame - a.frame) / (b.frame - a.frame)
    t = _ease(raw_t, a.easing)
    out = {}
    for key in ("x", "y", "scale", "scale_x", "scale_y", "rotation", "opacity"):
        av, bv = getattr(a, key), getattr(b, key)
        if av is not None and bv is not None:
            out[key] = av + (bv - av) * t
        else:
            out[key] = av if av is not None else bv
    return out


@dataclass
class DrawOp:
    """A single drawing operation on one animation frame."""
    tool: str                          # "brush" | "line" | "rect" | "ellipse" | "text" | "fill"
    pts: List[tuple] = field(default_factory=list)
    color: str = "#000000"
    width: int = 4
    text: str = ""
    fill_color: str = ""
    opacity: float = 1.0
    smooth: bool = True


@dataclass
class AnimationLayer:
    name: str
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    # frame_index -> list of DrawOp dicts
    frames: Dict[int, List[dict]] = field(default_factory=dict)
    keyframes: List[Keyframe] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def get_frame(self, index: int) -> List[dict]:
        return self.frames.get(index, [])

    def set_frame(self, index: int, ops: List[dict]):
        self.frames[index] = ops

    def clear_frame(self, index: int):
        self.frames.pop(index, None)


@dataclass
class AnimationProject:
    title: str = "Untitled Animation"
    width: int = 960
    height: int = 540
    fps: int = 12
    total_frames: int = 24
    background: str = "#FFFFFF"
    layers: List[AnimationLayer] = field(default_factory=lambda: [
        AnimationLayer("Background"),
        AnimationLayer("Drawing"),
        AnimationLayer("Foreground"),
    ])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_layer(self, name: str) -> AnimationLayer:
        layer = AnimationLayer(name)
        self.layers.append(layer)
        return layer

    def remove_layer(self, layer_id: str):
        self.layers = [l for l in self.layers if l.id != layer_id]

    def find_layer(self, layer_id: str) -> Optional[AnimationLayer]:
        return next((l for l in self.layers if l.id == layer_id), None)

    def active_layers(self) -> List[AnimationLayer]:
        return [l for l in self.layers if l.visible and not l.locked]


# ─────────────────────────────────────────────────────────────
#  Spreadsheet model
# ─────────────────────────────────────────────────────────────

@dataclass
class SpreadsheetCell:
    value: str = ""
    formula: str = ""
    bold: bool = False
    italic: bool = False
    align: str = "left"
    bg_color: str = ""
    fg_color: str = ""
    format: str = ""   # "number" | "currency" | "percent" | "date" | ""


@dataclass
class SpreadsheetSheet:
    name: str = "Sheet 1"
    rows: int = 50
    cols: int = 26
    cells: Dict[str, SpreadsheetCell] = field(default_factory=dict)  # "A1" -> cell
    col_widths: Dict[int, int] = field(default_factory=dict)
    row_heights: Dict[int, int] = field(default_factory=dict)
    frozen_rows: int = 0
    frozen_cols: int = 0
    id: str = field(default_factory=new_id)

    def cell(self, row: int, col: int) -> SpreadsheetCell:
        key = self._key(row, col)
        if key not in self.cells:
            self.cells[key] = SpreadsheetCell()
        return self.cells[key]

    @staticmethod
    def _key(row: int, col: int) -> str:
        letters = ""
        c = col
        while True:
            letters = chr(65 + c % 26) + letters
            c = c // 26 - 1
            if c < 0:
                break
        return f"{letters}{row + 1}"


@dataclass
class SpreadsheetProject:
    title: str = "Untitled Spreadsheet"
    sheets: List[SpreadsheetSheet] = field(default_factory=lambda: [SpreadsheetSheet()])

    def add_sheet(self, name: str = "") -> SpreadsheetSheet:
        n = name or f"Sheet {len(self.sheets) + 1}"
        s = SpreadsheetSheet(name=n)
        self.sheets.append(s)
        return s
