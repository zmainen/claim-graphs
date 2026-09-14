"""PandocSource: the formats pandoc reads reach the structured branch.

These exist because the PDF branch sat broken for the whole life of the repository (#47) and
nothing noticed: every paper in the only corpus was JATS, so the flat-text path was never
taken. A format nobody's corpus exercises needs its own test or it is a claim, not a feature.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claim_graphs.sources import BUILT_IN, FileSource, PandocSource, for_ref, registry  # noqa: E402

PAPER = """---
title: Thalamic bursting sharpens cortical orientation tuning
abstract: |
  Tuning width narrows by 31% during bursts.
---

# Results

Tuning width narrowed from 42.1 to 29.0 degrees (n = 412, p = 2.1e-9).

# Materials and methods

Recordings used 64-channel silicon probes.
"""

HAVE_PANDOC = shutil.which("pandoc") is not None


def _md(tmp: Path) -> Path:
    p = tmp / "paper.md"
    p.write_text(PAPER, encoding="utf-8")
    return p


def test_claims_what_pandoc_reads_and_nothing_else():
    """It must not shadow FileSource: .xml and .pdf are JATS and PDF already."""
    src = PandocSource()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assert src.handles(str(_md(tmp)))
        for suffix in (".xml", ".nxml", ".pdf"):
            f = tmp / f"other{suffix}"
            f.write_text("x", encoding="utf-8")
            assert not src.handles(str(f)), f"{suffix} belongs to FileSource"
        missing = tmp / "absent.md"
        assert not src.handles(str(missing)), "a path that is not a file is not handled"


def test_registered_after_the_built_ins_that_own_a_suffix():
    names = [s.name for s in registry()]
    assert names[:3] == ["elife", "file", "pandoc"]
    assert PandocSource in BUILT_IN


def test_markdown_routes_to_pandoc_and_xml_does_not():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assert for_ref(str(_md(tmp))).name == "pandoc"
        xml = tmp / "paper.xml"
        xml.write_text("<article/>", encoding="utf-8")
        assert for_ref(str(xml)).name == "file", "FileSource must keep JATS"


def test_missing_pandoc_says_so_by_name(monkeypatch=None):
    """The refusal must name pandoc, or the reader hunts for a missing adapter instead."""
    real = shutil.which
    try:
        shutil.which = lambda name: None            # noqa: ARG005
        try:
            PandocSource._pandoc()
        except RuntimeError as exc:
            assert "pandoc" in str(exc).lower()
            assert "install" in str(exc).lower()
        else:
            raise AssertionError("a missing pandoc must raise")
    finally:
        shutil.which = real


def test_resolves_markdown_to_jats_hashing_the_source():
    if not HAVE_PANDOC:
        print("skip: pandoc not installed")
        return
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        md = _md(tmp)
        r = PandocSource().resolve(str(md), cache_dir=tmp / "cache")

        assert r.format == "jats", "the point is to reach the structured branch"
        assert r.path.suffix == ".xml" and r.path.is_file()
        assert "<abstract>" in r.path.read_text(encoding="utf-8")

        # The hash is of the manuscript, not of the conversion: staleness asks whether the
        # input changed, and hashing pandoc's output would make every record depend on the
        # pandoc version.
        import hashlib
        assert r.sha256 == hashlib.sha256(md.read_bytes()).hexdigest()
        assert r.via and "pandoc" in r.via.lower()
        assert "converted by" in r.note


def test_editing_the_source_reconverts():
    if not HAVE_PANDOC:
        print("skip: pandoc not installed")
        return
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        md = _md(tmp)
        cache = tmp / "cache"
        first = PandocSource().resolve(str(md), cache_dir=cache)
        md.write_text(PAPER.replace("31%", "44%"), encoding="utf-8")
        second = PandocSource().resolve(str(md), cache_dir=cache)
        assert second.sha256 != first.sha256
        assert second.path != first.path, "a changed manuscript must not reuse the cache"
        assert "44%" in second.path.read_text(encoding="utf-8")


def test_refuses_a_format_it_cannot_offer():
    with tempfile.TemporaryDirectory() as d:
        md = _md(Path(d))
        try:
            PandocSource().resolve(str(md), prefer="pdf")
        except ValueError as exc:
            assert "pdf" in str(exc)
        else:
            raise AssertionError("pandoc produces jats; asking for pdf must fail")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
