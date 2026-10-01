#!/usr/bin/env python3
"""
narrate.py - speak text to a local audio file via VoiceStudio's local API.

Local-first, Arabic by default. VoiceStudio exposes an OpenAI-compatible endpoint
on the machine (no key on loopback). Claude Code calls this; the owner decides.
VoiceStudio is a separate AGPL-3.0 app the owner installed - this ONLY calls its
HTTP API and ships none of its code.

Usage:
  python narrate.py "النص" --out out.wav
  echo "long text" | python narrate.py - --out out.wav --voice alloy
  python narrate.py "..." --out out.wav --yes-download   # authorize the first ~2.3GB model fetch

Guards:
  - GET /health first; if VoiceStudio is down, print a clear message and exit
    (no silent failure, no partial file).
  - The FIRST generation may download the OmniVoice model (~2.3GB). Refused unless
    --yes-download is passed (owner's rule: ask before downloading a model). After
    one authorized run a marker lets later calls proceed without re-prompting.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_URL = os.environ.get("VOICESTUDIO_URL", "http://127.0.0.1:3900")
MODEL_OK_MARKER = os.path.expanduser("~/.claude/tools/.narrate_model_ok")


def _health(base):
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as r:
            d = json.loads(r.read().decode("utf-8"))
            return (d.get("status") == "ok"), d
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description="Speak text via the local VoiceStudio API.")
    ap.add_argument("text", help="text to speak, or - to read stdin")
    ap.add_argument("--out", required=True, help="output audio file path")
    ap.add_argument("--voice", default="alloy",
                    help="voice/timbre id (the spoken LANGUAGE comes from the text)")
    ap.add_argument("--model", default="tts-1")
    ap.add_argument("--format", default="wav", dest="fmt")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--yes-download", action="store_true",
                    help="authorize the first ~2.3GB OmniVoice model download")
    a = ap.parse_args()

    ok, info = _health(a.url)
    if not ok:
        sys.exit(f"ERROR: VoiceStudio is not reachable at {a.url} (/health: {info}). "
                 f"Start the VoiceStudio app, then retry.")

    if not os.path.exists(MODEL_OK_MARKER) and not a.yes_download:
        sys.exit("REFUSED: the first speech generation may download the OmniVoice "
                 "model (~2.3GB). Ask the owner, then re-run with --yes-download.")

    text = sys.stdin.read() if a.text == "-" else a.text
    if not text.strip():
        sys.exit("ERROR: empty text")

    payload = {"model": a.model, "voice": a.voice, "input": text,
               "response_format": a.fmt}
    req = urllib.request.Request(
        a.url + "/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: HTTP {e.code} from VoiceStudio.\n"
                 f"{e.read().decode('utf-8', 'replace')[:600]}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: request failed: {e}")

    with open(a.out, "wb") as f:
        f.write(audio)
    try:  # first success authorizes later calls without re-prompting
        os.makedirs(os.path.dirname(MODEL_OK_MARKER), exist_ok=True)
        open(MODEL_OK_MARKER, "a").close()
    except OSError:
        pass
    print(f"wrote {a.out} ({len(audio)} bytes) via {a.model}/{a.voice}")


if __name__ == "__main__":
    main()
