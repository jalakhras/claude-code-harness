#!/usr/bin/env python
"""Transcribe an audio/video file with faster-whisper.

Device policy (jalakhras): try CUDA (RTX 3070) first, fall back to CPU. The
caller (SKILL.md) tries platform captions before invoking this. Arabic is the
default language for trading videos. Output is timestamped Markdown.

Run via uv so deps resolve without polluting base Python:
  uv run --with faster-whisper --python 3.12 python transcribe.py <media> [--model large-v3] [--lang ar] [--out transcript.md]
"""
import argparse
import os
import sys
from pathlib import Path


def _cuda_dll_dirs():
    """Directories that may hold cuBLAS/cuDNN DLLs on Windows, best first.

    Proven on this machine: **Ollama ships its own CUDA runtime**, so
    `Ollama/lib/ollama/cuda_v12` provides cublas64_12.dll without installing any
    CUDA toolkit or pip package. cuDNN comes from the uv cache's nvidia packages
    when present. Without these on the loader path, CTranslate2 fails at encode
    with "cublas64_12.dll is not found" and transcription falls back to CPU
    (2-4.5h instead of ~40min for a long batch).
    """
    dirs = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        ollama = Path(local) / "Programs" / "Ollama" / "lib" / "ollama"
        for name in ("cuda_v12", "cuda_v13", "cuda_v11"):
            p = ollama / name
            if p.is_dir():
                dirs.append(p)
        # cuDNN (and any other nvidia libs) cached by uv
        cache = Path(local) / "uv" / "cache" / "archive-v0"
        if cache.is_dir():
            for pat in ("*/nvidia/*/bin", "*/Lib/site-packages/nvidia/*/bin"):
                dirs.extend(sorted(cache.glob(pat)))
    # nvidia packages installed in the current interpreter
    for base in sys.path:
        nv = Path(base) / "nvidia"
        if nv.is_dir():
            dirs.extend(sorted(nv.glob("*/bin")))
    seen, out = set(), []
    for d in dirs:
        s = str(d)
        if s not in seen:
            seen.add(s)
            out.append(d)
    return out


def add_cuda_dll_dirs() -> int:
    """Put the CUDA DLL dirs on the Windows loader path (PATH + add_dll_directory)
    before faster_whisper is imported. PATH matters: add_dll_directory alone did
    not resolve transitive dependencies here. Returns how many dirs were added."""
    if not hasattr(os, "add_dll_directory"):
        return 0
    added = 0
    for d in _cuda_dll_dirs():
        try:
            os.add_dll_directory(str(d))
        except OSError:
            pass
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        added += 1
    return added


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def try_groq(media, lang, prompt, engine):
    """Accurate, fast transcription via Groq's whisper-large-v3. CLOUD, opt-in only:
    used when engine == 'groq' (never automatically), because sending private
    trading content to the cloud must be a deliberate choice. Falls back to local
    (returns None) on any error incl. quota 429. Idea (owner): accurate free tier
    for general content, private local default for sensitive content."""
    import os
    if engine != "groq":
        return None  # privacy-first: local unless the caller explicitly opts in
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.stderr.write("[transcribe] engine=groq but GROQ_API_KEY not set; using local\n")
        return None
    try:
        size = Path(media).stat().st_size
    except OSError:
        return None
    if size > 24 * 1024 * 1024:  # Groq free upload cap ~25MB; larger => local
        sys.stderr.write("[transcribe] file >24MB; skipping Groq, using local\n")
        return None
    try:
        import json as _json
        import mimetypes
        import urllib.request
        boundary = "----harnessboundary"
        with open(media, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(str(media))[0] or "application/octet-stream"
        parts = []
        def field(name, value):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        field("model", "whisper-large-v3")
        field("response_format", "verbose_json")
        if lang:
            field("language", lang)
        if prompt:
            field("prompt", prompt)
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{Path(media).name}\"\r\n"
                      f"Content-Type: {ctype}\r\n\r\n").encode())
        body = b"".join(parts) + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions", data=body,
            headers={"Authorization": f"Bearer {key}", "User-Agent": "claude-harness/1.0",
                     "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            res = _json.loads(r.read().decode("utf-8"))
        segs = [type("S", (), {"start": s.get("start", 0.0), "text": s.get("text", "")})()
                for s in res.get("segments", [])]
        info = type("I", (), {"language": res.get("language", lang or "?"),
                              "language_probability": 1.0,
                              "duration": res.get("duration", 0.0)})()
        sys.stderr.write("[transcribe] Groq whisper-large-v3 (accurate tier)\n")
        return segs, info, "groq", "whisper-large-v3"
    except Exception as e:  # noqa: BLE001 - any error (quota/network) => local fallback
        sys.stderr.write(f"[transcribe] Groq unavailable ({str(e)[:120]}); using local\n")
        return None


def transcribe_on(model_name, device, compute, media, lang, prompt):
    """Load on a device and MATERIALIZE segments. CUDA can load fine but fail at
    encode (missing cuBLAS/cuDNN on Windows), so segments are consumed here inside
    the caller's try/except — that is the only place the real failure surfaces."""
    from faster_whisper import WhisperModel
    m = WhisperModel(model_name, device=device, compute_type=compute)
    seg_iter, info = m.transcribe(str(media), language=lang, initial_prompt=prompt or None, vad_filter=True)
    segments = list(seg_iter)  # force the work now so errors are catchable
    return segments, info, device, compute


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--model", default="large-v3")
    # "auto" (default) lets whisper detect the language — a real test showed an
    # Arabic default mis-transcribes English videos. Pass --lang ar for known
    # Arabic trading content to improve accuracy.
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--out", default="")
    ap.add_argument("--prompt", default="", help="initial_prompt: domain terms to bias decoding")
    ap.add_argument("--engine", choices=["local", "groq"], default="local",
                    help="local (private, default) or groq (cloud, opt-in, more accurate)")
    args = ap.parse_args()

    media = Path(args.media)
    if not media.exists():
        raise SystemExit(f"[transcribe] not found: {media}")

    # "auto"/"" => let whisper detect the language
    lang = None if args.lang.lower() in ("", "auto") else args.lang
    n = add_cuda_dll_dirs()
    if n:
        sys.stderr.write(f"[transcribe] added {n} nvidia DLL dir(s) for CUDA\n")

    # Tier 1: Groq accurate free tier (only if GROQ_API_KEY set + small file).
    # Tier 2/3: local GPU end-to-end, then CPU. cuBLAS/cuDNN failure surfaces at
    # encode, so load+encode are both inside the try.
    segments = info = device = compute = None
    groq = try_groq(media, lang, args.prompt, args.engine)
    if groq is not None:
        segments, info, device, compute = groq
    else:
        for dev, comp in (("cuda", "float16"), ("cpu", "int8")):
            try:
                sys.stderr.write(f"[transcribe] {args.model} on {dev}/{comp}, lang={lang or 'auto-detect'}\n")
                segments, info, device, compute = transcribe_on(args.model, dev, comp, media, lang, args.prompt)
                break
            except Exception as e:  # noqa: BLE001 - fall back on any CUDA/lib/runtime error
                sys.stderr.write(f"[transcribe] {dev} failed ({str(e)[:160]}); falling back\n")
    if segments is None:
        raise SystemExit("[transcribe] transcription failed on all engines")

    lines = [
        f"# Transcript — {media.name}",
        "",
        f"- model: {args.model} ({device}/{compute})",
        f"- language: {info.language} (p={info.language_probability:.2f})",
        f"- duration: {fmt_ts(info.duration)}",
        "",
        "## Segments",
        "",
    ]
    for seg in segments:
        lines.append(f"- **[{fmt_ts(seg.start)}]** {seg.text.strip()}")

    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")  # UTF-8, no BOM
        sys.stderr.write(f"[transcribe] wrote {args.out}\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
