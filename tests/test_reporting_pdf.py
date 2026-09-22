"""Tests for PDF export via Playwright."""
from __future__ import annotations
from pathlib import Path

import pytest

from reporting.export.pdf import (
    is_available,
    render_pdf,
    render_pdfs,
)


# ---------------------------------------------------------------- availability

def test_is_available_returns_bool():
    result = is_available()
    assert isinstance(result, bool)


# ---------------------------------------------------------------- errors

def test_render_pdf_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pdf(tmp_path / "does_not_exist.html")


def test_render_pdfs_empty_list():
    assert render_pdfs([]) == []


# ---------------------------------------------------------------- integration

_HAS_PW = is_available()
_REASON = "Playwright not installed or Chromium missing"


@pytest.mark.skipif(not _HAS_PW, reason=_REASON)
def test_render_tier1_pdf(synthetic_run_dir, tmp_path):
    from reporting.tiers.tier1_executive import build_tier1
    html = build_tier1(synthetic_run_dir,
                       output_path=tmp_path / "report_executive.html")
    pdf = render_pdf(html, pdf_path=tmp_path / "report_executive.pdf",
                     verbose=False)
    assert pdf.exists()
    # PDF magic bytes
    head = pdf.read_bytes()[:4]
    assert head == b"%PDF"
    # Non-trivial file
    assert pdf.stat().st_size > 20_000


@pytest.mark.skipif(not _HAS_PW, reason=_REASON)
def test_render_tier2_pdf(synthetic_run_dir, tmp_path):
    from reporting.tiers.tier2_research import build_tier2
    html = build_tier2(synthetic_run_dir,
                       output_path=tmp_path / "report_full.html")
    pdf = render_pdf(html, pdf_path=tmp_path / "report_full.pdf",
                     verbose=False)
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert pdf.stat().st_size > 20_000


@pytest.mark.skipif(not _HAS_PW, reason=_REASON)
def test_render_pdfs_batch(synthetic_run_dir, tmp_path):
    from reporting.tiers.tier1_executive import build_tier1
    h1 = build_tier1(synthetic_run_dir, output_path=tmp_path / "one.html")
    h2 = build_tier1(synthetic_run_dir, output_path=tmp_path / "two.html")
    pdfs = render_pdfs([(h1, tmp_path / "one.pdf"),
                        (h2, tmp_path / "two.pdf")],
                       verbose=False)
    assert len(pdfs) == 2
    for pdf in pdfs:
        assert pdf.exists()
        assert pdf.read_bytes()[:4] == b"%PDF"


@pytest.mark.skipif(not _HAS_PW, reason=_REASON)
def test_pdf_format_a4(synthetic_run_dir, tmp_path):
    from reporting.tiers.tier1_executive import build_tier1
    html = build_tier1(synthetic_run_dir, output_path=tmp_path / "a4.html")
    pdf = render_pdf(html, pdf_path=tmp_path / "a4.pdf",
                     pdf_format="A4", verbose=False)
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"