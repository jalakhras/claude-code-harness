---
name: media-ingest
description: Watch a video/audio source (URL, local file, or a folder of them) with care — the visuals matter. Downloads with yt-dlp, extracts scene frames with ffmpeg, and transcribes with faster-whisper on the local GPU (Arabic by default, timestamped), saving everything to the Obsidian vault. Use when jalakhras asks to watch a video, turn a strategy video/book into rules, or research from TED/YouTube. Hands off to strategy-codification or research-protocol.
metadata:
  origin: claude-harness
  lane: "5 (content/video), feeds lane 2 (trading tools) and lane 3 (research)"
allowed-tools: Bash, Read, Glob
---

# media-ingest

Turn a video/audio source into a timestamped transcript + selected frames stored
in the vault, then produce the asked output. **Read the frames with the
transcript — the visual elements matter** (jalakhras rule; trading charts,
diagrams, and on-screen text carry the meaning).

## Owner's rule — Claude runs it all itself | القاعدة

On any "analyze/watch video(s)" request, **Claude drives the whole local pipeline;
the owner runs nothing**: (1) ensure Ollama is up (start it if down), (2) run the
local pipeline (free — `batch_ingest.py` for a folder auto-starts Ollama and does
transcribe+frames+analysis per file), (3) read the per-video `analysis.md` (not
the raw transcripts) + frames, then finish the requested deliverable. Claude tokens
are spent only on the final synthesis/refinement, never on every raw transcript.

## Prerequisites (verified on this machine)

- `yt-dlp`, `ffmpeg`, `ffprobe` on PATH.
- `uv` for an isolated Python env — nothing pollutes base Python.
- **Prefer platform captions** (yt-dlp `--write-auto-subs`) — free, local, exact;
  no model needed. Only transcribe when captions are absent.
- GPU (RTX 3070) is best-effort: the script tries `cuda/float16` then **falls back
  to CPU automatically** if CUDA libs don't resolve (a known flaky Windows cuBLAS/
  cuDNN issue — do NOT force the `nvidia-*-cu12` uv packages; they shadowed the
  working system CUDA and broke it here). CPU works always (a 1-hour video ≈
  10–25 min on CPU vs 2–4 on GPU). For speed without local GPU, a Groq/OpenAI
  Whisper key via the `watch` skill is the alternative.

`SKILL_DIR` = the directory of THIS file (…/skills/media-ingest). Scripts are under
`$SKILL_DIR/scripts/`.

## Steps

### 1. Resolve the source and target
- **URL / online video** → download with yt-dlp. **Captions first:** if the
  platform has subtitles, use them (free, instant, exact) and skip transcription
  entirely. Only transcribe when there are no usable captions.
- local file → use as is; a folder (e.g. `Course 1\`) → process each in order.
- `TOPIC` = a short slug the user gives or you derive. Target vault dir:
  `<vault>\raw\videos\<TOPIC>\<video-name>\` (raw is read-only afterwards).

```bash
# URL: grab subtitles if present, and the media (for frames / no-caption fallback)
yt-dlp -f "bv*+ba/b" --write-auto-subs --write-subs --sub-langs "ar,en" \
  -o "<dir>/%(title)s.%(ext)s" "<URL>"
# if a .vtt/.srt was written, convert it to the transcript — no whisper, no cost.
```

### 2. Transcript — tiered, private by default
- **Captions first** (yt-dlp) — free, exact, no model.
- Else **local faster-whisper** (GPU float16 → CPU) — the default, private, free,
  and accurate for Arabic on `large-v3`.
- **Groq whisper-large-v3** is CLOUD and **opt-in only** (`--engine groq`), never
  automatic — sending private trading content to the cloud is a deliberate choice.
  On any error/quota it auto-falls back to local.

**Privacy rule:** sensitive content (the owner's strategies) stays **local** by
default. Use `--engine groq` only for general/non-sensitive material.

**Original language + Arabic:** transcription keeps the **original language**;
`batch_ingest.py --translate` also writes `transcript.ar.md`. Local analysis/
translation uses **aya-expanse:8b** (strong Arabic, private). For the most accurate
Arabic on general content, `--engine groq` uses **allam-2-7b** (a Saudi Arabic
model) on Groq's free tier, auto-falling back to local aya.

- Otherwise transcribe. **Language auto-detects by default** — pass
  `--lang ar` only for known-Arabic trading content (improves accuracy; a real
  test showed an Arabic default mis-transcribes English videos). Pass trading
  terms as a prompt to bias decoding:

```bash
uv run --with faster-whisper --python 3.12 python "$SKILL_DIR/scripts/transcribe.py" \
  "<media>" --model large-v3 --lang ar \
  --prompt "<comma-separated domain terms that bias decoding, e.g. product or field jargon>" \
  --out "<dir>/transcript.md"
```
Drop `--lang ar` for non-Arabic or unknown sources (auto-detect). Use
`--model tiny` only for a quick smoke test; `large-v3` for real work. The script
auto-falls back to CPU if GPU CUDA libs are unavailable — the run still succeeds.

### 3. Frames — scene-aware, capped
```bash
python "$SKILL_DIR/scripts/frames.py" "<media>" --out "<dir>/frames" --max 40
```
Read the saved frames alongside `transcript.md` before drawing conclusions.

### 4. Save to the vault, then summarize
- Files land in `<vault>\raw\videos\<TOPIC>\<video>\{transcript.md, frames/}`
  (raw = read-only). Write a short source page under `<vault>\wiki\sources\`
  with the required frontmatter and `[[wikilinks]]`, citing the raw files.

### 5. Hand off
- Strategy video/book → **`strategy-codification`** skill: it reads the per-video
  `analysis.md` files (not the raw transcripts), produces numbered testable rules
  with source timestamps, the non-automatable list, a falsification pass, and an
  indicator spec for the owner to approve — then Pine/MQL5 via `pine-*`.
- TED/lecture/market topic → **research-protocol**: sourced, dated claims;
  separate fact / inference / recommendation.

## Batch — hundreds of videos, free | تحليل مجاني للمئات

For many videos, analyzing each through Claude costs tokens. Instead, a **local
LLM (Ollama, free, offline)** drafts each video's analysis; Claude only refines
the important ones or synthesizes the aggregate. Zero tokens for the per-video pass.

```bash
# one command per folder; resumable
python "$SKILL_DIR/scripts/batch_ingest.py" "<folder>" --topic <slug> \
  --lang ar --llm qwen2.5:7b --mode rules --skip-existing
```
Per file it writes `<vault>/raw/videos/<slug>/<video>/{transcript.md, frames/,
analysis.md}`. `transcript.md` and `frames/` are local/free; `analysis.md` is the
local-LLM draft (free). Then Claude reads the `analysis.md` files (not the raw
transcripts) to synthesize — far fewer tokens.

- Ollama must be running (`ollama serve`) with the model pulled
  (`ollama pull qwen2.5:7b`). `analyze_local.py` calls `localhost:11434`.
- `--mode rules` for strategy videos (numbered testable rules); `--mode summary`
  otherwise. The local 7B model is a first pass — Claude refines nuance.

## Notes
- Whole folder (interactive, one at a time): loop step 1–4 per file. For scale,
  use `batch_ingest.py` above.
- Never write transcripts with a BOM (the ar.json/en.json trap); the script
  writes UTF-8 without BOM.
- Do not delete anything under `<vault>\raw` (vault rule).
