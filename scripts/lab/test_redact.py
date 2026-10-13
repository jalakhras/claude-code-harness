#!/usr/bin/env python
"""Spec for redact.py: the worker's SQL password never leaves the worker.

The literal value (from REDACT_LITERAL) is the primary defence — it catches the password in any
form, including with ';' or quotes in it. The connection-string pattern is the second layer, for
text the literal cannot reach (another password, a re-encoded one). Files: text results get both;
the HTML report gets the literal only (its own JS says `e.password=null` and must not change); a
binary that contains the literal (a trace.zip) is deleted — fail closed.
"""
import importlib.util
import io
import pathlib

spec = importlib.util.spec_from_file_location("redact", pathlib.Path(__file__).with_name("redact.py"))
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)

SECRET = "Xy9;q'Z\"Aa1!"   # contains ; and both quotes on purpose


def test_line_redacts_the_literal_and_every_connection_string_shape():
    cases = [
        f"Server=127.0.0.1,1433;User Id=sa;Password={SECRET};TrustServerCertificate=True",
        "Password=abc;x", "password = abc", "PWD=abc", 'Password="abc"', "Password='abc'",
        "Password=&quot;abc&quot;;", "Pwd=&#39;abc&#39;",
    ]
    for c in cases:
        out = rd.redact_line(c, SECRET)
        assert SECRET not in out and "abc" not in out, (c, out)
        assert "***" in out


def test_line_without_secrets_is_unchanged():
    assert rd.redact_line("[dotnet-run] progress: Domain.Tests 445 done", SECRET) == \
        "[dotnet-run] progress: Domain.Tests 445 done"


def test_stream_mode_passes_lines_through_redacted():
    src = io.StringIO(f"ok\nUser Id=sa;Password={SECRET};x\n")
    dst = io.StringIO()
    rd.redact_stream(src, dst, SECRET)
    assert dst.getvalue() == "ok\nUser Id=sa;Password=***;x\n"


def test_files_mode(tmp_path):
    trx = tmp_path / "dotnet" / "A.trx"; trx.parent.mkdir()
    trx.write_text(f"<Message>Server=x;Password={SECRET};</Message>", encoding="utf-8")
    html = tmp_path / "report" / "index.html"; html.parent.mkdir()
    html.write_text(f"async function U(e){{e.password=null}} leaked={SECRET}", encoding="utf-8")
    zipf = tmp_path / "trace.zip"
    zipf.write_bytes(b"PK\x03\x04" + SECRET.encode() + b"\x00\x01")
    clean = tmp_path / "ok.zip"
    clean.write_bytes(b"PK\x03\x04 nothing here")

    report = rd.redact_tree(tmp_path, SECRET)

    assert SECRET not in trx.read_text(encoding="utf-8") and "Password=***" in trx.read_text(encoding="utf-8")
    h = html.read_text(encoding="utf-8")
    assert SECRET not in h and "e.password=null" in h          # report JS untouched
    assert not zipf.exists() and clean.exists()                 # fail closed on the binary hit
    assert report["deleted"] == [str(zipf)]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
