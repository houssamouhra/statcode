from __future__ import annotations

import argparse
import os
import shutil
import sys
import textwrap
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "2.1.0"

# Colour helpers (disabled when TERM=dumb)
_IS_TTY = sys.stdout.isatty() and os.getenv("TERM", "dumb").lower() != "dumb"
YELLOW = "\033[33m" if _IS_TTY else ""
RED = "\033[31m" if _IS_TTY else ""
BOLD = "\033[1m" if _IS_TTY else ""
UNDERLINE = "\033[4m" if _IS_TTY else ""
END = "\033[0m" if _IS_TTY else ""


@cache
def _load_yaml(name: str) -> dict[str, Any]:
    """Load a YAML data file from the distribution or package resources."""
    import yaml

    candidates: list[Path] = []

    # Nuitka standalone layout: <binary_dir>/statcode-data/<name>
    frozen = getattr(sys, "frozen", False) or "__compiled__" in globals()
    if frozen:
        candidates.append(
            Path(sys.executable).resolve().parent / "statcode-data" / name
        )
    else:
        # Still try argv-based path (covers some install layouts)
        candidates.append(Path(sys.argv[0]).resolve().parent / "statcode-data" / name)

    # Development / next to this source file
    candidates.append(Path(__file__).resolve().parent / name)

    for path in candidates:
        if path.is_file():
            with path.open(encoding="utf-8") as file:
                return yaml.safe_load(file)

    # Proper installed package (wheel / editable via importlib.resources)
    try:
        resource = resources.files(__package__).joinpath(name)
        with resource.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except (TypeError, AttributeError, FileNotFoundError, OSError) as exc:
        raise FileNotFoundError(
            f"Could not find data file {name!r}. Searched: "
            + ", ".join(str(p) for p in candidates)
        ) from exc


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


@cache
def _copyright_text(is_status_code: bool) -> str:
    data = _load_yaml("copyright_description.yml")
    return data["statuscode"] if is_status_code else data["headers"]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _make_scrollable(widget: urwid.Widget) -> urwid.Widget:

    import urwid

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

        def keypress(self, key):
            if key in ("up", "k"):
                self._trim_top = max(0, self._trim_top - 1)
                self._invalidate()
            elif key in ("down", "j"):
                self._trim_top += 1
                self._invalidate()
            else:
                return key

    return _Scrollable(widget)


def format_plain_text(key: str) -> str | None:
    """Format a status code or header without building urwid widgets."""
    try:
        descriptions, is_code, normalised = get_descriptions(key)
        entry = descriptions[normalised]
    except KeyError:
        return None

    width = shutil.get_terminal_size().columns
    indent = " " * 5
    body_width = max(1, width - len(indent))

    title = "STATUS MESSAGE" if is_code else "HEADER INFO"
    identifier = str(normalised)
    message = entry.get("message", "Unknown")

    if is_code:
        heading = f"{identifier}: {message}"
    else:
        heading = f"{identifier}, Example= {message}"

    def wrap_body(text: str) -> str:
        return textwrap.fill(
            text,
            width=body_width,
            initial_indent=indent,
            subsequent_indent=indent,
        )

    sections = [
        f" {title}\n{wrap_body(heading)}",
        f" CATEGORY\n{wrap_body(entry.get('category', 'Not available'))}",
        f" DESCRIPTION\n{wrap_body(entry.get('description', 'Not available'))}",
        f" COPYRIGHT\n{wrap_body(_copyright_text(is_code))}",
    ]

    header = "STATCODE: The Manual for HTTP Status Codes and Headers".center(width)

    return f"{header}\n\n" + "\n\n".join(sections)


def generate_content(key: str) -> urwid.Widget | None:

    import urwid

    """Build the main content widget for a status code or header."""
    try:
        descriptions, is_code, normalised = get_descriptions(key)
        entry = descriptions[normalised]
    except KeyError:
        return None

    def section(title: str) -> urwid.Text:
        return urwid.Text(("title", title))

    def body(text: str) -> urwid.Padding:
        return urwid.Padding(
            urwid.Text(f"{text}\n"),
            left=5,
        )

    def header_line(
        attr: str,
        identifier: str,
        separator: str,
    ) -> urwid.Text:
        return urwid.Text(
            [
                (attr, identifier),
                ("default", separator),
                ("message", entry.get("message", "Unknown")),
                ("default", "\n"),
            ]
        )

    if is_code:
        code_class = normalised // 100
        code_attr = {
            1: "info",
            2: "success",
            3: "redirect",
            4: "clienterr",
            5: "servererr",
        }.get(code_class, "code")

        heading = header_line(code_attr, str(normalised), ": ")
        main_title = "STATUS MESSAGE"
    else:
        heading = header_line("code", str(normalised), ", Example= ")
        main_title = "HEADER INFO"

    content_sections = [
        section(main_title),
        urwid.Padding(heading, left=5),
        section("CATEGORY"),
        body(entry.get("category", "Not available")),
        section("DESCRIPTION"),
        body(entry.get("description", "Not available")),
        section("COPYRIGHT"),
        body(_copyright_text(is_code)),
    ]

    pile = urwid.Pile(
        [
            urwid.Text(
                (
                    "header",
                    "STATCODE: The Manual for HTTP Status Codes and Headers\n",
                ),
                align="center",
            ),
            *content_sections,
        ]
    )

    return urwid.Padding(
        _make_scrollable(pile),
        left=1,
        right=1,
    )


class App:
    """Simple full-screen TUI."""

    PALETTE: ClassVar[list[tuple[str, ...]]] = [
        ("menu", "black", "light cyan", "standout"),
        ("title", "default,bold", "default", "bold"),
        ("header", "dark cyan", "default"),
        ("code", "yellow,bold", "default"),
        ("message", "default,bold", "default"),
        ("info", "light blue,bold", "default"),
        ("success", "light green,bold", "default"),
        ("redirect", "yellow,bold", "default"),
        ("clienterr", "light red,bold", "default"),
        ("servererr", "light magenta,bold", "default"),
    ]

    def __init__(self, body: urwid.Widget) -> None:

        import urwid

        footer = urwid.Text(["\n", ("menu", " Q "), ("light gray", " Quit")])
        layout = urwid.Frame(body=body, footer=footer)
        loop = urwid.MainLoop(
            layout,
            self.PALETTE,
            unhandled_input=self._handle_input,
            handle_mouse=True,
        )
        try:
            loop.run()
        except KeyboardInterrupt:
            pass

    @staticmethod
    def _handle_input(key: str) -> None:
        if key in ("q", "Q"):
            import urwid

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


class StatcodeArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return (
            f"\n"
            f"{BOLD}Like man pages, but for HTTP status codes.{END}\n\n"
            f"{UNDERLINE}USAGE{END}\n"
            f"  {BOLD}statcode{END} "
            f"{YELLOW}<status_code|header>{END}\n"
            f"  {BOLD}statcode{END} "
            f"{YELLOW}--list <statuscode|headers>{END}\n\n"
            f"{UNDERLINE}OPTIONS{END}\n"
            f"  {BOLD}-h, --help{END}            "
            "Show this help message\n"
            f"  {BOLD}-a, -l, --all, --list{END} "
            f"{YELLOW}{{statuscode,headers}}{END}\n"
            "                        List all status codes or headers\n"
            f"  {BOLD}-n, --no-ui{END}           "
            "Force plain-text output\n"
            f"  {BOLD}-v, --version{END}         "
            "Show statcode version\n\n"
            f"{BOLD}Made by @shobrook & Fixed by @houssamouhra{END}\n"
        )

    def error(self, message: str) -> None:
        if message.startswith("unrecognized arguments: "):
            unknown = message.removeprefix("unrecognized arguments: ")
            self.exit(
                2,
                f"{RED}error: unknown option {unknown}{END}\n"
                f"Try '{YELLOW}{self.prog} --help{END}' for usage.\n",
            )

        if ("expected one argument" in message and "--list" in message) or (
            "invalid choice" in message and "--list" in message
        ):
            self.exit(
                2,
                f"{RED}error: --list requires a value: "
                f"{{statuscode,headers}}\n{END}"
                f"Try '{YELLOW}{self.prog} --help{END}' for usage.\n",
            )


def print_all(kind: str) -> None:
    if kind == "statuscode":
        data, is_code, _ = get_descriptions("200")
    else:
        data, is_code, _ = get_descriptions("Accept")

    for key, value in data.items():
        msg = value["message"] if is_code else ""
        print(f"{RED}{key}:{END} {msg}")


def main() -> None:
    parser = StatcodeArgumentParser(
        prog="statcode",
        add_help=False,
    )

    parser.add_argument(
        "key",
        nargs="?",
        help="HTTP status code or header name",
    )

    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    parser.add_argument(
        "-n",
        "--no-ui",
        action="store_true",
        help="force plain-text output",
    )

    parser.add_argument(
        "-a",
        "-l",
        "--all",
        "--list",
        choices=("statuscode", "headers"),
        dest="list_kind",
        help="list all status codes or headers",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
        help="Show the version and exit",
    )

    args = parser.parse_args()

    if args.list_kind:
        print_all(args.list_kind)
        return

    if args.key is None:
        parser.print_help()
        return

    if args.no_ui or not _IS_TTY:
        output = format_plain_text(args.key)

        if output is None:
            print(f"{RED}Sorry, statcode doesn't recognize: {args.key}{END}")
            return

        print(output)
        return

    content = generate_content(args.key)

    if content is None:
        print(f"{RED}Sorry, statcode doesn't recognize: {args.key}{END}")
        return

    try:
        App(content)
    except Exception:  # noqa: BLE001 – fall back on any TUI failure
        output_without_ui(content)


if __name__ == "__main__":
    main()
