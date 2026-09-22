"""
PDF export via Playwright.

Renders an HTML report to a PDF using headless Chromium. Preserves all
CSS (including the cream/clay palette), interactive Plotly charts become
static SVG in the PDF, and page breaks follow the @media print rules.

Setup (one-time):
    pip install playwright
    python -m playwright install chromium

Usage:
    from reporting.export.pdf import render_pdf, render_pdfs
    render_pdf("path/to/report.html", "path/to/report.pdf")
    render_pdfs([(html1, pdf1), (html2, pdf2)])
"""
from __future__ import annotations
from pathlib import Path


# ---------------------------------------------------------------- availability

def is_available() -> bool:
    """True if Playwright package is installed AND Chromium is available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is not installed. To enable PDF export:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium"
        ) from e


# ---------------------------------------------------------------- rendering

def render_pdfs(
    jobs: list[tuple[str | Path, str | Path | None]],
    pdf_format: str = "Letter",
    margin_mm: int = 12,
    print_background: bool = True,
    scale: float = 1.0,
    wait_ms: int = 2500,
    verbose: bool = True,
) -> list[Path]:
    """
    Render multiple HTML files to PDFs in a single browser session.

    Args:
        jobs: list of (html_path, pdf_path). If pdf_path is None, it is
              derived from the html_path by replacing the extension.
        pdf_format: "Letter" | "A4" | "Legal" | "Tabloid"
        margin_mm: uniform page margin in millimetres (bottom gets +6mm)
        print_background: whether to include background colors
        scale: browser zoom factor (0.5 to 2.0)
        wait_ms: extra delay after page load to let Plotly render
        verbose: print progress per file

    Returns:
        list of written PDF paths, in the same order as `jobs`.
    """
    if not jobs:
        return []

    sync_playwright = _import_playwright()

    # Normalize jobs
    norm: list[tuple[Path, Path]] = []
    for html, pdf in jobs:
        html_p = Path(html).resolve()
        if not html_p.exists():
            raise FileNotFoundError(f"HTML not found: {html_p}")
        if pdf is None:
            pdf_p = html_p.with_suffix(".pdf")
        else:
            pdf_p = Path(pdf).resolve()
            pdf_p.parent.mkdir(parents=True, exist_ok=True)
        norm.append((html_p, pdf_p))

    written: list[Path] = []

    footer_template = (
        "<div style='"
        "font-family: -apple-system, Helvetica, Arial, sans-serif;"
        "font-size: 8px;"
        "color: #95928A;"
        "width: 100%;"
        "padding: 0 12mm;"
        "display: flex; justify-content: space-between;"
        "'>"
        "  <span>QuantForge</span>"
        "  <span>Page <span class='pageNumber'></span>"
        "  of <span class='totalPages'></span></span>"
        "</div>"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            for html_p, pdf_p in norm:
                if verbose:
                    print(f"    → rendering {html_p.name} ...", end=" ", flush=True)

                page = browser.new_page()
                try:
                    page.goto(html_p.as_uri(), wait_until="networkidle")
                    # Plotly renders async. Wait for the SVG elements
                    # to appear, then add a small buffer.
                    try:
                        page.wait_for_function(
                            "() => document.querySelectorAll('.plotly-graph-div .main-svg').length > 0",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    page.wait_for_timeout(wait_ms)

                    page.pdf(
                        path=str(pdf_p),
                        format=pdf_format,
                        print_background=print_background,
                        scale=scale,
                        prefer_css_page_size=False,
                        margin={
                            "top":    f"{margin_mm}mm",
                            "bottom": f"{margin_mm + 6}mm",
                            "left":   f"{margin_mm}mm",
                            "right":  f"{margin_mm}mm",
                        },
                        display_header_footer=True,
                        header_template="<div></div>",
                        footer_template=footer_template,
                    )
                finally:
                    page.close()

                if verbose:
                    size_kb = pdf_p.stat().st_size / 1024
                    print(f"✅ {pdf_p.name} ({size_kb:,.0f} KB)")

                written.append(pdf_p)
        finally:
            browser.close()

    return written


def render_pdf(
    html_path: str | Path,
    pdf_path: str | Path | None = None,
    **kwargs,
) -> Path:
    """Render a single HTML file to PDF. Returns the written path."""
    results = render_pdfs([(html_path, pdf_path)], **kwargs)
    return results[0]