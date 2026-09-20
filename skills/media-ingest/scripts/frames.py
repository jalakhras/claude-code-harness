#!/usr/bin/env python
"""Extract scene-change frames from a video with ffmpeg, capped at N.

Visuals matter for jalakhras's trading videos, so frames are read alongside the
transcript. Scene detection picks meaningful frames; a fallback samples evenly.

Usage:
  python frames.py <video> --out <dir> [--max 40] [--threshold 0.3]
Requires ffmpeg + ffprobe on PATH.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration_seconds(video: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--threshold", type=float, default=0.3, help="scene score 0..1")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        raise SystemExit(f"[frames] not found: {video}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Scene-change frames, numbered, downscaled to 1280 wide.
    scene = out / "scene_%03d.jpg"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
        "-vf", f"select='gt(scene,{args.threshold})',scale=1280:-1",
        "-vsync", "vfr", "-frames:v", str(args.max), "-q:v", "3", str(scene),
    ]
    subprocess.run(cmd, check=False)
    got = sorted(out.glob("scene_*.jpg"))

    # Fallback: if scene detection found too few, sample evenly.
    if len(got) < 3:
        dur = duration_seconds(str(video))
        n = min(args.max, 12)
        if dur > 0 and n > 0:
            fps = n / dur
            even = out / "even_%03d.jpg"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                "-vf", f"fps={fps:.6f},scale=1280:-1", "-frames:v", str(n),
                "-q:v", "3", str(even),
            ], check=False)
            got = sorted(out.glob("*.jpg"))

    sys.stderr.write(f"[frames] extracted {len(got)} frames to {out}\n")
    for g in got:
        print(g.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
