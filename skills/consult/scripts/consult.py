#!/usr/bin/env python3
"""
consult.py - on-demand second opinion from a Gemini model (Google AI Studio API).

Claude Code uses this as an ADVISOR only: send a prompt, read the model's answer,
then Claude Code + the owner weigh it and decide. It is never the final authority
(see rules/80-performance.md "Agent & model routing"; rules/65-roles.md).

Key is read from the environment (GEMINI_API_KEY) or a private git-ignored file -
never passed on the command line, never printed. stdlib only (no SDK install).

Usage:
  python consult.py --list                              # models this key can call
  python consult.py "your question"                     # default: gemini-3.8-flash (free), output capped
  python consult.py --max 800 "longer question"         # raise the output cap
  echo "long prompt" | python consult.py --model gemini-flash-latest -
  CONSULT_ALLOW_PAID=1 python consult.py --model gemini-pro-latest "critical decision"

Guards:
  - Default model is free-tier flash; output is capped (--max, default 400 tokens)
    so a reply cannot flood the caller's context. Thinking is disabled for a
    concise answer that fits the cap.
  - Any PAID (Pro) model is refused unless CONSULT_ALLOW_PAID=1 is set.

Privacy: the prompt leaves the machine to Google (free tier may train on it).
Never send sensitive/proprietary/trading content - use the local Ollama path for that.
"""
import json
import os
import sys
import urllib.request
import urllib.error

# UTF-8 output regardless of the Windows console codepage.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.8-flash"   # current free-tier flash
DEFAULT_MAX_TOKENS = 800             # cap the visible answer; raise with --max when needed
PREAMBLE = ("You are a second opinion for an engineer who makes the final decision. "
            "Be concise, state your key assumptions, and end with ONE clear "
            "recommendation. Do not pad.")

# Where the key may live (first hit wins). env var takes priority over all.
KEY_PATHS = [
    os.path.expanduser("~/.claude/tools/.gemini_key"),
    os.path.expanduser("~/.claude/.gemini_key"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gemini_key"),
]


def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        for p in KEY_PATHS:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    k = f.read().strip()
                if k:
                    break
            except OSError:
                continue
    if not k:
        sys.exit("ERROR: no API key. Set GEMINI_API_KEY, or put the key (one line) "
                 "in ~/.claude/tools/.gemini_key")
    return k


def _is_paid(model):
    # Free tier = flash / flash-lite / gemma. Pro models are paid.
    return "pro" in model.lower()


def _http(url, data=None):
    headers = {"Content-Type": "application/json", "User-Agent": "harness-consult/1.0"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: HTTP {e.code} from Gemini API.\n"
                 f"{e.read().decode('utf-8', 'replace')[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: cannot reach Gemini API: {e}")


def list_models():
    d = _http(f"{API_ROOT}/models?key={_key()}")
    for m in d.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(m.get("name", "").replace("models/", ""))


def ask(model, prompt, max_tokens):
    if _is_paid(model) and os.environ.get("CONSULT_ALLOW_PAID", "") != "1":
        sys.exit(f"REFUSED: '{model}' is a PAID model. Re-run with CONSULT_ALLOW_PAID=1 "
                 f"to authorize a paid call, or use a free flash model.")
    url = f"{API_ROOT}/models/{model}:generateContent?key={_key()}"
    payload = {
        "contents": [{"parts": [{"text": PREAMBLE + "\n\n" + prompt}]}],
        # Disable extended thinking: a concise second opinion needs none, and
        # thinking tokens otherwise consume the output budget (empty MAX_TOKENS).
        "generationConfig": {"maxOutputTokens": max_tokens,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    d = _http(url, payload)
    cands = d.get("candidates", [])
    if not cands:
        sys.exit(f"ERROR: no answer (response: {json.dumps(d)[:400]})")
    parts = cands[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    u = d.get("usageMetadata", {})
    tag = "PAID" if _is_paid(model) else "free"
    print(f"--- {model} [{tag}] | tokens in/out: "
          f"{u.get('promptTokenCount', '?')}/{u.get('candidatesTokenCount', '?')} | "
          f"finish: {cands[0].get('finishReason', '?')} ---")
    print(text if text else "(empty - try a higher --max)")


def main(argv):
    args = argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--list":
        return list_models()
    model = DEFAULT_MODEL
    max_tokens = DEFAULT_MAX_TOKENS
    while args and args[0] in ("--model", "--max"):
        if len(args) < 2:
            sys.exit(f"ERROR: {args[0]} needs a value")
        if args[0] == "--model":
            model = args[1]
        else:
            try:
                max_tokens = int(args[1])
            except ValueError:
                sys.exit("ERROR: --max needs an integer")
        args = args[2:]
    if not args:
        sys.exit("ERROR: no prompt given")
    prompt = sys.stdin.read() if args == ["-"] else " ".join(args)
    if not prompt.strip():
        sys.exit("ERROR: empty prompt")
    ask(model, prompt, max_tokens)


if __name__ == "__main__":
    main(sys.argv)
