#!/usr/bin/env python
"""Batch-ingest a folder of videos: transcribe + frames + local analysis, free.

For jalakhras's hundreds of videos. Per file: transcript (local whisper, CPU
fallback), scene frames, and a local-LLM analysis (Ollama) — zero Claude tokens.
Claude only reviews the aggregate afterward. Everything lands in the vault.

Usage:
  python batch_ingest.py <folder> --topic <slug> [--vault <vault-root>]
    [--model large-v3] [--lang ar] [--llm qwen2.5:7b] [--mode rules|summary]
    [--frames 24] [--skip-existing]

Idempotent with --skip-existing: a video whose transcript.md already exists is
skipped, so a long batch can resume.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4a", ".mp3", ".wav"}


def run(cmd):
    sys.stderr.write("  $ " + " ".join(str(c) for c in cmd[:6]) + " ...\n")
    return subprocess.run(cmd).returncode


def ensure_ollama(host="http://localhost:11434"):
    """Start the local Ollama server if it is not already responding."""
    def up():
        try:
            urllib.request.urlopen(host + "/api/version", timeout=3)
            return True
        except Exception:  # noqa: BLE001
            return False
    if up():
        return True
    # locate ollama.exe (Windows default install) or rely on PATH
    exe = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    exe = exe if os.path.exists(exe) else "ollama"
    try:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[batch] could not start Ollama ({e}); analysis will be skipped\n")
        return False
    for _ in range(20):
        time.sleep(1)
        if up():
            sys.stderr.write("[batch] Ollama server started\n")
            return True
    sys.stderr.write("[batch] Ollama did not come up; analysis will be skipped\n")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--vault", default=r"<vault>")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--llm", default="aya-expanse:8b")
    ap.add_argument("--mode", default="rules")
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--translate", action="store_true",
                    help="also write transcript.ar.md (Arabic) when source is not Arabic")
    ap.add_argument("--engine", choices=["local", "groq"], default="local",
                    help="local (private, default) or groq (cloud, opt-in, more accurate)")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        raise SystemExit(f"[batch] not a folder: {folder}")
    vids = sorted(p for p in folder.rglob("*") if p.suffix.lower() in VIDEO_EXT)
    if not vids:
        raise SystemExit(f"[batch] no media under {folder}")

    raw = Path(args.vault) / "raw" / "videos" / args.topic
    done, skipped, failed = 0, 0, 0
    llm_ok = ensure_ollama()
    sys.stderr.write(f"[batch] {len(vids)} media files -> {raw} (local LLM: {'up' if llm_ok else 'unavailable'})\n")

    for i, v in enumerate(vids, 1):
        outdir = raw / v.stem
        outdir.mkdir(parents=True, exist_ok=True)
        transcript = outdir / "transcript.md"
        sys.stderr.write(f"\n[{i}/{len(vids)}] {v.name}\n")

        if args.skip_existing and transcript.exists():
            sys.stderr.write("  skip (transcript exists)\n"); skipped += 1; continue

        # 1. transcribe (local whisper via uv; GPU->CPU fallback inside the script)
        rc = run([
            "uv", "run", "--with", "faster-whisper", "--python", "3.12", "python",
            str(HERE / "transcribe.py"), str(v),
            "--model", args.model, "--lang", args.lang, "--engine", args.engine, "--out", str(transcript),
        ])
        if rc != 0 or not transcript.exists():
            sys.stderr.write("  transcribe FAILED\n"); failed += 1; continue

        # 2. frames (local ffmpeg)
        run(["python", str(HERE / "frames.py"), str(v), "--out", str(outdir / "frames"), "--max", str(args.frames)])

        # 3. local analysis + optional Arabic translation (Ollama; free).
        if llm_ok:
            run(["python", str(HERE / "analyze_local.py"), str(transcript),
                 "--model", args.llm, "--mode", args.mode, "--engine", args.engine, "--out", str(outdir / "analysis.md")])
            # Idea (owner): keep the original language AND an Arabic translation,
            # both local/free. Translate only when the source is not already Arabic.
            if args.translate and "- language: ar " not in transcript.read_text(encoding="utf-8", errors="ignore"):
                run(["python", str(HERE / "analyze_local.py"), str(transcript),
                     "--model", args.llm, "--mode", "translate", "--engine", args.engine, "--out", str(outdir / "transcript.ar.md")])
        done += 1

    sys.stderr.write(f"\n[batch] done={done} skipped={skipped} failed={failed}. Raw in {raw}\n")
    sys.stderr.write("[batch] next: Claude synthesizes/refines from the per-video analysis.md files.\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
