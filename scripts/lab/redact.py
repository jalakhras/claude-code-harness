#!/usr/bin/env python3
"""Keep the worker's SQL password on the worker.

  redact.py stream            # stdin -> stdout, line by line (wraps the live test output)
  redact.py tree <dir>        # evidence folder, in place, before it is copied back

The literal password comes from the REDACT_LITERAL environment variable (never an argument, so it
is not on a command line). It is the primary defence: it catches the value in any shape, with ';'
or quotes inside. The connection-string pattern is the second layer for text the literal cannot
reach. In a tree, text results get both; the HTML report gets the literal only (its bundled JS
contains `e.password=null`, which the pattern would break); a binary file that contains the
literal (e.g. a trace.zip) is deleted — fail closed — and named in the report.
"""
import os
import re
import sys
from pathlib import Path

MASK = "***"
#: password / pwd, any case, optional spaces, an optional quote (plain or XML-escaped), the value
PATTERN = re.compile(r"(?i)((?:password|pwd)\s*=\s*)(?:&quot;|&apos;|&#39;|\"|')?[^;<\r\n]*")
#: results where the connection-string pattern is safe to apply
TEXT_RESULTS = {".trx", ".xml", ".txt", ".log", ".md", ".json"}
#: text files that get the literal only
LITERAL_ONLY = {".html", ".htm", ".js", ".css", ".svg"}


def redact_line(line: str, literal: str) -> str:
    if literal:
        line = line.replace(literal, MASK)
    return PATTERN.sub(lambda m: m.group(1) + MASK, line)


def redact_stream(src, dst, literal: str) -> None:
    for line in src:
        dst.write(redact_line(line, literal))
        dst.flush()


def redact_tree(root, literal: str) -> dict:
    report = {"rewritten": [], "deleted": []}
    needle = literal.encode("utf-8") if literal else b""
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in TEXT_RESULTS or ext in LITERAL_ONLY:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            if ext in TEXT_RESULTS:
                new = "".join(redact_line(l, literal) for l in text.splitlines(keepends=True))
            else:
                new = text.replace(literal, MASK) if literal else text
            if new != text:
                path.write_text(new, encoding="utf-8", errors="surrogateescape")
                report["rewritten"].append(str(path))
        elif needle and needle in path.read_bytes():
            path.unlink()
            report["deleted"].append(str(path))
    return report


def main(argv) -> int:
    literal = os.environ.get("REDACT_LITERAL", "")
    if len(argv) >= 2 and argv[1] == "stream":
        redact_stream(sys.stdin, sys.stdout, literal)
        return 0
    if len(argv) >= 3 and argv[1] == "tree":
        r = redact_tree(argv[2], literal)
        if r["rewritten"] or r["deleted"]:
            print(f"[redact] evidence: {len(r['rewritten'])} file(s) redacted, "
                  f"{len(r['deleted'])} binary file(s) deleted (held the password)")
        for d in r["deleted"]:
            print(f"[redact] deleted {Path(d).name}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
