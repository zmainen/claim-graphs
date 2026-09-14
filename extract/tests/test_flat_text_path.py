"""The flat-text branch of prepare(): the one no corpus exercises.

`prepare()` sends JATS to `parse_jats` and everything else here. Every paper in the eLife
corpus is JATS, so this branch was never taken — and it sat broken for the entire life of the
repository (#47): `extract_figure_captions` referenced `PANEL_LABEL_RE`, a name defined
nowhere, and raised NameError on any input that reached it. `make check` imports the module,
which is not enough to catch a name that is only looked up when its line runs.

This is the path an adopter with no publisher API uses first, so it is tested here rather than
left to whoever tries it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claim_graphs.prepare import extract_figure_captions, slice_sections  # noqa: E402

PAPER = """Thalamic bursting sharpens cortical orientation tuning

Abstract

Tuning width narrows by 31% during bursts.

Introduction

Thalamic relay neurons fire in tonic and burst modes.

Results

Tuning width narrowed from 42.1 to 29.0 degrees (n = 412, p = 2.1e-9).

Figure 1. Tuning sharpens during bursts. (A) Tonic epochs. (B) Burst epochs.

The effect survived a rate-matched control.

Figure 2. Controls. (A-C) Rate matching, shuffle, and jitter.

Discussion

Burst firing may act as a gain control.

Materials and methods

Recordings used 64-channel silicon probes.
"""


def test_captions_are_found_without_raising():
    """The regression: this raised NameError for every input before #47."""
    caps = extract_figure_captions(PAPER)
    assert len(caps) == 2, f"expected two figures, got {[c.figure_num for c in caps]}"
    assert [c.figure_num for c in caps] == ["1", "2"]


def test_panel_ranges_expand():
    """Shares `_panel_letters` with parse_jats, so "(A-C)" is three panels on either path.

    The block this replaced took single letters only, so it would have read "(A-C)" as no
    panels at all — the two branches disagreeing about the same caption.
    """
    caps = {c.figure_num: c for c in extract_figure_captions(PAPER)}
    assert caps["1"].panels == ["a", "b"]
    assert caps["2"].panels == ["a", "b", "c"], "a range must expand, not be dropped"


def test_sections_slice_from_flat_text():
    sections = slice_sections(PAPER)
    for name in ("abstract", "results", "methods"):
        assert sections.get(name), f"{name} came back empty"
    assert "42.1" in sections["results"]
    # "Materials and methods" and "Methods" are the same section under two house styles.
    assert "silicon probes" in sections["methods"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
