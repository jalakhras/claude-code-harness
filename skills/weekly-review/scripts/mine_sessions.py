#!/usr/bin/env python
"""Mine Claude Code conversations for what the owner keeps correcting and keeps asking for.

The growth log only holds what was written down at session end; the conversations hold the
rest. This pulls the OWNER'S OWN WORDS out of the transcripts (no tool output, no harness
reminders, no subagent briefs, no pasted material), masks secrets, and writes a compact
digest. A second, optional pass hands the digest to a LOCAL model (Ollama) to draft
candidate lessons and candidate skills. Nothing leaves the machine; Claude reads only the
small result, never the raw transcripts.

Usage:
  python mine_sessions.py extract [--since auto|YYYY-MM-DD] [--root ~/.claude/projects]
                                  [--growth-log <vault>/growth-log.md] [--out digest.md]
  python mine_sessions.py analyze <digest.md> [--model aya-expanse:8b] [--host http://localhost:11434]
                                  [--out candidates.md]
"""
import argparse
import os
import json
import re
import sys
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_MAX_CHARS = 600
DEFAULT_CHUNK_CHARS = 12000
DEFAULT_WINDOW_DAYS = 7
CUT_MARK = " …[cut]"
OLLAMA_TIMEOUT_S = 600

_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_PASTED = re.compile(r"<pasted_content\b[^>]*>.*?</pasted_content\b[^>]*>", re.S)
_CMD_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.S)
_CMD_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
# A message that opens with a harness tag (<browser_instruction>, <ide_opened_file>,
# <local-command-stdout>, ...) is the harness talking. Those names always carry "_" or "-";
# plain HTML tags never do, so an owner message starting with "<div>" is kept. A list of
# known tags missed new ones on the first real run.
_WRAPPER = re.compile(r"^<[a-z][a-z0-9]*[_-][a-z0-9_-]*[\s>]")
_HARNESS_LINES = ("[Request interrupted",)
_PASTE_MARK = "[pasted]"
_NOT_OWNER_FLAGS = ("isSidechain", "isMeta", "isCompactSummary", "isVisibleInTranscriptOnly")
_REVIEWED = re.compile(r"^--- reviewed (\d{4}-\d{2}-\d{2})", re.M)

# Secrets: the key name (when there is one) stays so the line still reads; the value goes.
_SECRETS = [
    # No \b before the key: DB_PASSWORD= and access_token= must match; a JSON quote may sit before the
    # colon; \s* crosses a line break, so a value on its own line goes too.
    (re.compile(r"""(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|كلمة المرور|كلمة السر)["']?)"""
                r"""(\s*[=:]\s*)["']?[^\s"',;}]+"""), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{10,}"), r"\1 [REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[REDACTED]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED]"),
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), "[REDACTED]"),
    (re.compile(r"\b[a-fA-F0-9]{40,}\b"), "[REDACTED]"),
]

ANALYZE_PROMPT = (
    "You are reviewing one week of messages a software engineer sent to an AI coding assistant.\n"
    "Find ONLY patterns that are actually present in the messages below. Do not invent.\n\n"
    "Output three sections in English (keep quotes in their original language, verbatim):\n"
    "## Corrections\n"
    "Each time the engineer told the assistant it was wrong, restated a preference, or said\n"
    "'I told you'. One bullet each: the preference in one line, then the quote and its date.\n"
    "## Repeated workflows\n"
    "Kinds of request that appear 2 or more times (same job, maybe different wording). One bullet\n"
    "each: a short name, how many times, the dates, one quote.\n"
    "## Skill candidates\n"
    "For each repeated workflow worth automating: skill-name (kebab-case), when it should trigger\n"
    "(the engineer's own words), and the steps the engineer expects, numbered.\n"
    "If a section has nothing, write 'none'.\n\n"
    "=== MESSAGES ===\n"
)


def redact(text: str) -> str:
    for pattern, repl in _SECRETS:
        text = pattern.sub(repl, text)
    return text


def _content_text(content):
    """The text of a message's content, or None when it carries no text (tool results only)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(parts) if parts else None


def owner_text(record):
    """The owner's own words in one transcript record, or None when the record is not that."""
    if not isinstance(record, dict) or record.get("type") != "user":
        return None
    if any(record.get(flag) for flag in _NOT_OWNER_FLAGS):
        return None
    # Automated turns (claude-mem's observer, task notifications) are "user" records too.
    # turnOrigin decides where present (the desktop app sends the owner's prompts via the SDK);
    # only a record without it falls back to the entrypoint.
    origin = record.get("turnOrigin")
    if origin is not None:
        if origin != "human":
            return None
    elif str(record.get("entrypoint", "")).startswith("sdk-"):
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    text = _content_text(message.get("content"))
    if text is None:
        return None
    text = _REMINDER.sub("", text)
    name = _CMD_NAME.search(text)
    if name:
        args = _CMD_ARGS.search(text)
        text = (name.group(1).strip() + " " + (args.group(1).strip() if args else "")).strip()
    text = _PASTED.sub(_PASTE_MARK, text).strip()
    if not text or text == _PASTE_MARK or _WRAPPER.match(text) or text.startswith(_HARNESS_LINES):
        return None
    return text


def _parse_ts(value):
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def last_review_date(growth_log: Path, now=None):
    """Start of the window: the latest '--- reviewed YYYY-MM-DD' divider, else a week back."""
    now = now or datetime.now(timezone.utc)
    try:
        # errors="replace": a log saved as ANSI (PowerShell 5.1 Add-Content) keeps its ASCII dividers.
        found = _REVIEWED.findall(growth_log.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        found = []
    dates = []
    for value in found:
        try:
            dates.append(datetime.fromisoformat(value))
        except ValueError:
            sys.stderr.write(f"[mine] ignored a bad divider date: {value}\n")
    if dates:
        return max(dates).replace(tzinfo=timezone.utc)
    start = now - timedelta(days=DEFAULT_WINDOW_DAYS)
    return datetime(start.year, start.month, start.day, tzinfo=timezone.utc)


def _project_name(record, file_path: Path):
    cwd = str(record.get("cwd") or "").rstrip("\\/")
    return re.split(r"[\\/]", cwd)[-1] if cwd else file_path.parent.name


def extract(root: Path, since: datetime, max_chars: int = DEFAULT_MAX_CHARS):
    """Owner messages from top-level session files under root, newer than since, oldest first.
    Subagent transcripts live one level deeper and are never read: their 'user' turns are
    briefs Claude wrote, not the owner."""
    out = []
    for path in sorted(root.glob("*/*.jsonl")):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < since:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            sys.stderr.write(f"[mine] skipped {path.name}: {exc}\n")
            continue
        for line in lines:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            ts = _parse_ts(record.get("timestamp")) if isinstance(record, dict) else None
            if ts is None or ts < since:
                continue
            text = owner_text(record)
            if text is None:
                continue
            text = redact(text)  # before the cut: a cut secret no longer looks like one
            if len(text) > max_chars:
                text = text[:max_chars] + CUT_MARK
            out.append({"ts": ts.strftime("%Y-%m-%d %H:%M"), "project": _project_name(record, path),
                        "session": record.get("sessionId") or path.stem, "text": text})
    out.sort(key=lambda m: m["ts"])
    return out


def render_digest(msgs, since: datetime) -> str:
    groups = OrderedDict()
    for m in msgs:
        groups.setdefault(m["project"], []).append(m)
    lines = [f"# Owner messages since {since:%Y-%m-%d}", "",
             f"- messages: {len(msgs)} · projects: {len(groups)} · secrets masked", ""]
    for project, items in sorted(groups.items()):
        lines.append(f"## {project}")
        lines.append("")
        for m in items:
            text = redact(m["text"])  # before the join: a value on its own line stays a value
            one_line = " ⏎ ".join(part.strip() for part in text.splitlines() if part.strip())
            lines.append(f"- **{m['ts']}** {one_line}")
        lines.append("")
    return "\n".join(lines)


def _chunks(text: str, size: int):
    chunk, used = [], 0
    for line in text.splitlines(keepends=True):
        if chunk and used + len(line) > size:
            yield "".join(chunk)
            chunk, used = [], 0
        chunk.append(line)
        used += len(line)
    if chunk:
        yield "".join(chunk)


def analyze(digest: str, generate, chunk_chars: int = DEFAULT_CHUNK_CHARS) -> str:
    """Run the digest through generate(prompt) in line-aligned chunks; Claude merges the parts."""
    parts = list(_chunks(digest, chunk_chars))
    answers = []
    for i, part in enumerate(parts, 1):
        reply = (generate(ANALYZE_PROMPT + part) or "").strip() or "(no answer from the model for this part)"
        answers.append(f"### Part {i}/{len(parts)}\n\n{reply}\n")
    return "\n".join(answers)


def ollama_body(model: str, prompt: str) -> dict:
    # keep_alive 0: unload the model as soon as it answers, so the GPU is free (rule 80).
    return {"model": model, "prompt": prompt, "stream": False, "keep_alive": 0}


def _ollama(host: str, model: str):
    def generate(prompt):
        req = urllib.request.Request(f"{host}/api/generate",
                                     data=json.dumps(ollama_body(model, prompt)).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8")).get("response", "")
    return generate


def _write_or_print(text: str, out: str):
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        sys.stderr.write(f"[mine] wrote {out}\n")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    ex.add_argument("--since", default="auto", help="auto (last review) or YYYY-MM-DD")
    ex.add_argument("--growth-log", default=str(Path(os.environ.get("HARNESS_VAULT", Path.home() / "Brain")) / "growth-log.md"),
                    help="default: $HARNESS_VAULT/growth-log.md, else ~/Brain/growth-log.md")
    ex.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ex.add_argument("--out", default="")
    an = sub.add_parser("analyze")
    an.add_argument("digest")
    an.add_argument("--model", default="aya-expanse:8b")
    an.add_argument("--host", default="http://localhost:11434")
    an.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS)
    an.add_argument("--out", default="")
    args = ap.parse_args(argv)

    if args.cmd == "extract":
        if args.since == "auto":
            since = last_review_date(Path(args.growth_log))
        else:
            since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        msgs = extract(Path(args.root), since, args.max_chars)
        _write_or_print(render_digest(msgs, since), args.out)
        sys.stderr.write(f"[mine] {len(msgs)} owner messages since {since:%Y-%m-%d}\n")
        return 0

    digest = Path(args.digest).read_text(encoding="utf-8")
    try:
        result = analyze(digest, _ollama(args.host, args.model), args.chunk_chars)
    except OSError as exc:
        raise SystemExit(f"[mine] local Ollama failed ({exc}). Is it up and '{args.model}' pulled?")
    header = f"# Candidates from {Path(args.digest).name}\n\n- model: {args.model} (local, draft — verify every item)\n\n"
    _write_or_print(header + result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
