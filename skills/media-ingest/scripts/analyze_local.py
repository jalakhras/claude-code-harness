#!/usr/bin/env python
"""Analyze a transcript with a LOCAL LLM via Ollama — free, offline, no tokens.

This is the "free for hundreds of videos" path: a local model drafts a summary
and candidate numbered rules per video; Claude only refines the important ones
later. No data leaves the machine.

Usage:
  python analyze_local.py <transcript.md> [--model qwen2.5:7b] [--mode summary|rules]
    [--out analysis.md] [--host http://localhost:11434] [--lang ar]

Requires Ollama running (`ollama serve`) with the model pulled.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

# qwen (and some local models) occasionally leak CJK characters into Arabic
# output even when told not to. Strip them deterministically as a safety net so a
# saved file never contains Chinese/Japanese runs. Best with a good Arabic model.
_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿豈-﫿＀-￯]+")


def strip_cjk(text: str) -> str:
    return _CJK.sub("", text)

PROMPTS = {
    "summary": (
        "أنت محلّل خبير. أمامك تفريغ فيديو. اكتب ملخصاً دقيقاً ومنظّماً بالعربية:\n"
        "- الفكرة الرئيسية في سطرين.\n- النقاط الأساسية (نقاط مرقّمة).\n"
        "- المصطلحات المهمة.\n- ما يحتاج تدقيقاً بشرياً.\n"
        "التزم بما ورد في التفريغ فقط؛ لا تخترع. اذكر الطابع الزمني حين يفيد.\n\n"
    ),
    "rules": (
        "أنت خبير تداول تحوّل شرح استراتيجية إلى قواعد قابلة للاختبار. من التفريغ التالي استخرج:\n"
        "- قواعد مرقّمة، كل قاعدة: الشرط ⇐ النتيجة (والاستثناء إن وُجد)، مع الطابع الزمني للمصدر.\n"
        "- قائمة الحقائق غير القابلة للأتمتة (اختيار الفريم، المعايرة، التقدير البصري).\n"
        "- أسئلة/غموض يحتاج تأكيداً بشرياً.\n"
        "التزم بالتفريغ حرفياً؛ لا تضف قواعد من عندك. بالعربية.\n\n"
    ),
    "translate": (
        "ترجم التفريغ التالي إلى العربية الفصحى ترجمةً دقيقة وأمينة، محافظاً على المعنى "
        "والمصطلحات التقنية والطوابع الزمنية كما هي. لا تلخّص ولا تحذف؛ ترجمة كاملة سطراً بسطر.\n"
        "أخرج **بالعربية حصراً**. يُمنع منعاً باتاً استخدام أي حروف صينية أو يابانية أو "
        "أي لغة أخرى؛ أسماء العلم والمصطلحات التقنية الإنجليزية فقط تُكتب بالإنجليزية عند اللزوم.\n\n"
    ),
}

# Appended to every prompt to suppress a known qwen artifact (stray CJK characters).
_ARABIC_GUARD = ("\n\n[تعليمة إخراج صارمة: اكتب بالعربية فقط. لا تستخدم أي حروف صينية "
                 "(CJK) أو لغات أخرى. المصطلحات التقنية الإنجليزية فقط عند الضرورة.]")


def ollama_generate(host: str, model: str, prompt: str) -> str:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8")).get("response", "").strip()


def groq_generate(model: str, prompt: str):
    """CLOUD, opt-in: accurate Arabic via Groq's free tier (e.g. openai/gpt-oss-120b
    or allam-2-7b). Returns text, or None to fall back to local on any error/quota.
    Only called when engine == 'groq' — private content stays local by default."""
    import os
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.stderr.write("[analyze] engine=groq but GROQ_API_KEY not set; using local\n")
        return None
    try:
        # System message carries the Arabic-only guard so the model does not echo it.
        sys_msg = "اكتب بالعربية الفصحى فقط. لا تستخدم أي حروف صينية أو لغات أخرى. المصطلحات التقنية الإنجليزية فقط عند الضرورة. لا تكرّر هذه التعليمات في مخرجاتك."
        body = json.dumps({"model": model, "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}]}).encode("utf-8")
        # Groq is behind a WAF that 403s urllib's default UA — send an explicit one.
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "User-Agent": "claude-harness/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            res = json.loads(r.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 - any error/quota => local fallback
        sys.stderr.write(f"[analyze] Groq unavailable ({str(e)[:120]}); using local\n")
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--model", default="aya-expanse:8b")
    ap.add_argument("--mode", choices=list(PROMPTS), default="summary")
    ap.add_argument("--out", default="")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--engine", choices=["local", "groq"], default="local",
                    help="local (private aya, default) or groq (cloud, opt-in, more accurate)")
    ap.add_argument("--groq-model", default="allam-2-7b",
                    help="Groq model when --engine groq (e.g. allam-2-7b for Arabic)")
    args = ap.parse_args()

    tp = Path(args.transcript)
    if not tp.exists():
        raise SystemExit(f"[analyze] not found: {tp}")
    transcript = tp.read_text(encoding="utf-8")

    prompt = PROMPTS[args.mode] + "=== التفريغ ===\n" + transcript + _ARABIC_GUARD

    out = None
    used = f"{args.model} (local)"
    if args.engine == "groq":
        out = groq_generate(args.groq_model, prompt)          # cloud, opt-in
        if out is not None:
            used = f"{args.groq_model} (Groq cloud)"
    if out is None:                                            # local default / fallback
        try:
            out = ollama_generate(args.host, args.model, prompt)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"[analyze] local Ollama failed ({e}). Is the server up and '{args.model}' pulled?")

    out = strip_cjk(out)  # guarantee no CJK leakage in the saved file
    header = f"# Analysis ({args.mode}) — {tp.stem}\n\n- model: {used}\n- source: {tp.name}\n\n"
    text = header + out + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")  # UTF-8, no BOM
        sys.stderr.write(f"[analyze] wrote {args.out}\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
