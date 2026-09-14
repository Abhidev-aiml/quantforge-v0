"""
Shared visual theme for all QuantForge charts.

Anthropic-inspired light theme: warm cream background, dark charcoal
text, one warm clay accent, subtle borders, generous whitespace.
Serif headers, sans body, monospace numbers.

One source of truth for colors, fonts, spacing. Every chart function
calls `apply_theme(fig)` before returning.
"""
from __future__ import annotations
import plotly.graph_objects as go


# ---- palette ---------------------------------------------------------

COLORS = {
    # surfaces
    "bg":            "#FAF9F5",   # page background (warm cream)
    "panel":         "#FFFFFF",   # card background
    "panel_alt":     "#F5F4ED",   # nested / hover
    "border":        "#E8E6DD",   # subtle warm border
    "border_strong": "#D6D3C7",   # emphasised border

    # text
    "text":          "#1F1F1F",   # primary dark charcoal
    "text_muted":    "#6B6B6B",   # secondary
    "text_subtle":   "#95928A",   # tertiary / captions

    # accents
    "accent":        "#D97757",   # Claude clay / warm orange
    "accent_soft":   "#F2DACF",   # light tint of accent
    "accent_dark":   "#B85A38",   # darker accent for lines on light bg

    # semantic
    "positive":      "#4A7C59",   # muted forest green
    "positive_soft": "#E3EDE4",   # light tint
    "negative":      "#B23A2E",   # muted brick red
    "negative_soft": "#F4DEDB",   # light tint
    "warning":       "#C68A2E",   # amber
    "info":          "#4A6FA5",   # muted navy

    # chart-specific
    "bench":         "#B8B5AA",   # benchmark line (warm gray)
    "grid":          "#EDEBE3",   # faint grid
    "zeroline":      "#D6D3C7",   # zero baseline

    # backwards-compatible aliases (so existing chart code still works)
    "muted":         "#6B6B6B",
    "neutral":       "#95928A",
}

# Font stacks — serif for headings, sans for body, mono for numbers
FONT_SERIF = "'Tiempos Headline', 'Charter', Georgia, 'Times New Roman', serif"
FONT_SANS  = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif"
FONT_MONO  = "'JetBrains Mono', 'SF Mono', 'Menlo', 'Consolas', ui-monospace, monospace"

# Plotly uses a single family string. Mono for axis/hover numbers.
FONT_PLOTLY = FONT_MONO


# ---- base layout -----------------------------------------------------

def base_layout(height: int = 340) -> dict:
    """Base Plotly layout dict for the light institutional theme."""
    return dict(
        height=height,
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font=dict(color=COLORS["text"], family=FONT_PLOTLY, size=11),
        margin=dict(l=62, r=28, t=32, b=46),
        xaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor=COLORS["border"],
            zerolinecolor=COLORS["zeroline"],
            showgrid=True,
            showline=False,
            ticks="outside",
            tickcolor=COLORS["border"],
            tickfont=dict(size=10, color=COLORS["text_subtle"]),
            title_font=dict(size=11, color=COLORS["text_muted"]),
        ),
        yaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor=COLORS["border"],
            zerolinecolor=COLORS["zeroline"],
            showgrid=True,
            showline=False,
            ticks="outside",
            tickcolor=COLORS["border"],
            tickfont=dict(size=10, color=COLORS["text_subtle"]),
            title_font=dict(size=11, color=COLORS["text_muted"]),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=COLORS["text_muted"]),
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=COLORS["panel"],
            bordercolor=COLORS["border_strong"],
            font=dict(family=FONT_PLOTLY, size=11, color=COLORS["text"]),
        ),
    )


def apply_theme(fig: go.Figure, height: int = 340) -> go.Figure:
    """Apply the base theme to a Plotly figure. Returns the same figure."""
    fig.update_layout(**base_layout(height=height))
    return fig


def empty_figure(message: str = "Not enough data to plot") -> go.Figure:
    """Return a themed empty figure with a caption-style annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(color=COLORS["text_subtle"], size=12, family=FONT_PLOTLY),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return apply_theme(fig, height=200)


# ---- formatting helpers ---------------------------------------------

def pct(x: float, decimals: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x*100:+.{decimals}f}%"


def ratio(x: float, decimals: int = 3) -> str:
    if x is None:
        return "—"
    return f"{x:+.{decimals}f}"