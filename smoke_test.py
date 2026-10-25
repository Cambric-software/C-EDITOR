"""Repeatable no-window smoke tests for the suite's core project models."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from suite_core import (
    ScenePage, SceneObject,
    TimelineProject, TimelineTrack, TimelineClip,
    AnimationProject, AnimationLayer,
    Keyframe, interpolate,
    SpreadsheetProject, SpreadsheetSheet,
)


def run():
    # ── design canvas ─────────────────────────────────────────────────────────
    page = ScenePage()
    img  = page.add("image", path="sample.png")
    page.add("text", text="Hello")
    page.reorder(img.id, 1)
    assert page.objects[1].kind == "image", "reorder failed"
    page.bring_forward(img.id)
    page.send_backward(img.id)
    removed = page.find(img.id)
    assert removed is not None, "find failed"
    page.remove(img.id)
    assert page.find(img.id) is None, "remove failed"

    # ── timeline ──────────────────────────────────────────────────────────────
    video = TimelineProject()
    assert len(video.tracks) == 6, "default tracks"
    vtrack = video.track("video")
    assert vtrack is not None, "no video track"
    clip = vtrack.add_clip("clip.mp4", start=1.2, end=8.0)
    assert clip.end == 8.0
    new_track = video.add_track("Overlay", "overlay")
    assert len(video.tracks) == 7
    vtrack.remove_clip(clip.id)
    assert len(vtrack.clips) == 0
    marker = video.add_marker(5.0, "Scene 2")
    assert marker.time == 5.0

    # ── animation keyframes ───────────────────────────────────────────────────
    anim  = AnimationProject()
    assert len(anim.layers) == 3, "default layers"
    layer = anim.layers[1]
    layer.keyframes = [
        Keyframe(0,  x=0,   opacity=0.0, easing="ease-in"),
        Keyframe(10, x=100, opacity=1.0),
    ]
    mid = interpolate(layer.keyframes[0], layer.keyframes[1], 5)
    # ease-in at t=0.5 → t²=0.25, so x≈25; check it's non-zero and not full
    assert 0 < mid["x"] < 100, f"x interpolation off: {mid['x']}"
    assert 0 < mid["opacity"] < 1, f"opacity off: {mid['opacity']}"
    # linear midpoint check (no easing)
    kf_lin = [Keyframe(0, x=0, opacity=0.0), Keyframe(10, x=100, opacity=1.0)]
    mid_lin = interpolate(kf_lin[0], kf_lin[1], 5)
    assert mid_lin["x"] == 50.0, f"linear x off: {mid_lin['x']}"
    assert mid_lin["opacity"] == 0.5, f"linear opacity off: {mid_lin['opacity']}"

    layer.set_frame(0, [{"tool":"Brush","pts":[(0,0),(10,10)],"color":"#000","width":3}])
    assert len(layer.get_frame(0)) == 1
    layer.clear_frame(0)
    assert layer.get_frame(0) == []

    new_layer = anim.add_layer("FX")
    assert len(anim.layers) == 4
    anim.remove_layer(new_layer.id)
    assert len(anim.layers) == 3

    # ── spreadsheet ───────────────────────────────────────────────────────────
    sp = SpreadsheetProject()
    s2 = sp.add_sheet("Data")
    assert len(sp.sheets) == 2
    cell = sp.sheets[0].cell(0, 0)
    cell.value = "42"; cell.bold = True
    assert sp.sheets[0].cell(0, 0).value == "42"
    assert sp.sheets[0]._key(0, 0) == "A1"
    assert sp.sheets[0]._key(0, 25) == "Z1"
    assert sp.sheets[0]._key(0, 26) == "AA1"

    # ── serialisation round-trip ──────────────────────────────────────────────
    payload = {
        "scene":     page.background,
        "timeline":  video.width,
        "animation": anim.fps,
        "sheet":     sp.sheets[0].name,
    }
    assert json.loads(json.dumps(payload)) == payload, "JSON round-trip failed"


if __name__ == "__main__":
    for i in range(25):
        run()
    print("25 core-suite smoke passes: OK")
