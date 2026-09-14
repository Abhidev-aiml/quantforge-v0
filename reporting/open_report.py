"""
Cross-platform "open this file in the default app" helper.

Respects an `auto_open` mode from config: ask | always | never.
Falls back to "never" if stdin isn't a TTY (CI, piped output).
"""
from __future__ import annotations
import sys
import webbrowser
from pathlib import Path


def open_in_browser(
    path: str | Path,
    mode: str = "ask",
    prompt: str | None = None,
) -> bool:
    """
    Open `path` in the default browser.

    Args:
        path: file to open
        mode: 'ask' | 'always' | 'never'
        prompt: custom prompt text for 'ask' mode

    Returns:
        True if the file was opened, False otherwise.
    """
    p = Path(path)
    if not p.exists():
        print(f"⚠️  Cannot open: file not found — {p}", file=sys.stderr)
        return False

    mode = (mode or "ask").lower()

    # Non-interactive context: never block on input
    if mode == "ask" and not sys.stdin.isatty():
        mode = "never"

    if mode == "never":
        return False

    if mode == "always":
        return _open(p)

    # mode == 'ask'
    msg = prompt or f"Open in browser? [Y/n] "
    try:
        answer = input(msg).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if answer in ("", "y", "yes"):
        return _open(p)
    return False


def _open(path: Path) -> bool:
    try:
        webbrowser.open(path.resolve().as_uri())
        return True
    except Exception as e:
        print(f"⚠️  Could not open browser: {e}", file=sys.stderr)
        return False
