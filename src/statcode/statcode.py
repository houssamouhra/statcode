from __future__ import annotations

import os
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import urwid
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "2.1.0"

# Colour helpers (disabled when TERM=dumb)
_IS_TTY = os.getenv("TERM", "dumb").lower() != "dumb"
YELLOW = "\033[33m" if _IS_TTY else ""
RED = "\033[31m" if _IS_TTY else ""
BOLD = "\033[1m" if _IS_TTY else ""
UNDERLINE = "\033[4m" if _IS_TTY else ""
END = "\033[0m" if _IS_TTY else ""


def _load_yaml(name: str) -> dict[str, Any]:
    """Load a YAML data file that lives next to this module."""
    try:
        # Preferred modern way (works with wheels / editable installs)
        ref = resources.files(__package__).joinpath(name)
        with ref.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (TypeError, AttributeError, FileNotFoundError):
        # Fallback for very old Python / weird environments
        path = Path(__file__).parent / name
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def get_descriptions(key: str) -> tuple[dict[str, Any], bool, str | int]:
    """
    Return (dictionary, is_status_code, normalised_key).

    is_status_code is True when the key was an integer status code.
    """
    try:
        code = int(key)
        data = _load_yaml("code_descriptions.yml")
        return data, True, code
    except (TypeError, ValueError):
        data = _load_yaml("header_descriptions.yml")
        return data, False, key


def _copyright_text(is_status_code: bool) -> str:
    data = _load_yaml("copyright_description.yml")
    return data["statuscode"] if is_status_code else data["headers"]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _make_scrollable(widget: urwid.Widget) -> urwid.Widget:
    """Prefer urwid’s built-in Scrollable; fall back to a minimal implementation."""
    if hasattr(urwid, "Scrollable"):
        return urwid.Scrollable(widget)

    # Minimal fallback for very old urwid (should almost never be needed)
    class _Scrollable(urwid.WidgetDecoration):
        def sizing(self):
            return frozenset([urwid.BOX])

        def selectable(self):
            return True

        def __init__(self, w):
            self._trim_top = 0
            super().__init__(w)

        def render(self, size, focus=False):
            maxcol, maxrow = size
            ow = self._original_widget
            canv = urwid.CompositeCanvas(ow.render((maxcol,), focus))
            if canv.rows() > maxrow:
                canv.trim(self._trim_top)
                canv.trim_end(canv.rows() - maxrow)
            return canv

        def keypress(self, size, key):
            if key in ("up", "k"):
                self._trim_top = max(0, self._trim_top - 1)
                self._invalidate()
            elif key in ("down", "j"):
                self._trim_top += 1
                self._invalidate()
            else:
                return key

    return _Scrollable(widget)


def generate_content(key: str) -> urwid.Widget | None:
    """Build the main content widget for a status code or header."""
    try:
        descriptions, is_code, normalised = get_descriptions(key)
        entry = descriptions[normalised]
    except KeyError:
        return None

    title = "STATUS MESSAGE" if is_code else "HEADER INFO"
    message_prefix = f"{normalised}: " if is_code else f"{normalised}, Example= "

    pile = urwid.Pile(
        [
            urwid.Text(
                "STATCODE: The Manual for HTTP Status Codes and Headers\n",
                align="center",
            ),
            urwid.Text(("title", title)),
            urwid.Padding(
                urwid.Text(message_prefix + entry["message"] + "\n"),
                left=5,
            ),
            urwid.Text(("title", "CATEGORY")),
            urwid.Padding(urwid.Text(entry["category"] + "\n"), left=5),
            urwid.Text(("title", "DESCRIPTION")),
            urwid.Padding(urwid.Text(entry["description"] + "\n"), left=5),
            urwid.Text(("title", "COPYRIGHT")),
            urwid.Padding(urwid.Text(_copyright_text(is_code) + "\n"), left=5),
        ]
    )

    return urwid.Padding(_make_scrollable(pile), left=1, right=1)


class App:
    """Simple full-screen TUI."""

    PALETTE = [
        ("menu", "black", "light cyan", "standout"),
        ("title", "default,bold", "default", "bold"),
    ]

    def __init__(self, body: urwid.Widget) -> None:
        footer = urwid.Text(["\n", ("menu", " Q "), ("light gray", " Quit")])
        layout = urwid.Frame(body=body, footer=footer)
        loop = urwid.MainLoop(
            layout,
            self.PALETTE,
            unhandled_input=self._handle_input,
            handle_mouse=True,
        )
        loop.run()

    @staticmethod
    def _handle_input(key: str) -> None:
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()


def output_without_ui(widget: urwid.Widget) -> None:
    """Render the widget to plain text (for pipes / dumb terminals)."""
    cols, rows = shutil.get_terminal_size()
    canvas = widget.render((cols, rows))
    text = "\n".join(line.decode("utf-8") for line in canvas.text).rstrip()
    print(text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_help() -> None:
    print(
        f"{BOLD}statcode v{VERSION} – Made by @shobrook & Refactored by @houssamouhra{END}\n"
    )
    print("Like man pages, but for HTTP status codes.\n")
    print(f"{UNDERLINE}Usage:{END} $ statcode {YELLOW}<status_code|header>{END}")
    print(f"{BOLD}-h, --help{END}                 show this help")
    print(f"{BOLD}-a, -l, --all, --list{END} statuscode   list all status codes")
    print(f"{BOLD}-a, -l, --all, --list{END} headers      list all headers")
    print(f"{BOLD}-n, --no-ui{END}                force plain-text output")


def print_all(kind: str) -> None:
    if kind == "statuscode":
        data, is_code, _ = get_descriptions("200")
    else:
        data, is_code, _ = get_descriptions("Accept")

    for key, value in data.items():
        msg = value["message"] if is_code else ""
        print(f"{RED}{key}:{END} {msg}")


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    if not args or args[0] in ("-h", "--help"):
        print_help()
        return

    if args[0] in ("-a", "-l", "--all", "--list"):
        if len(args) < 2 or args[1] not in ("statuscode", "headers"):
            print(f"{BOLD}Wrong parameter – see --help{END}")
            return
        print_all(args[1])
        return

    key = sys.argv[1]  # keep original case for headers
    no_ui = len(sys.argv) > 2 and sys.argv[2].lower() in ("-n", "--no-ui")

    content = generate_content(key)
    if content is None:
        print(f"{RED}Sorry, statcode doesn't recognize: {key}{END}")
        return

    if no_ui or not _IS_TTY:
        output_without_ui(content)
    else:
        try:
            App(content)
        except Exception:  # noqa: BLE001 – fall back on any TUI failure
            output_without_ui(content)


if __name__ == "__main__":
    main()
