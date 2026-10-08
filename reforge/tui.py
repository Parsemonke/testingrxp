"""Tiny terminal UI toolkit: colors, banner, arrow-key menus. Standard library only.

Arrow-key menus use msvcrt (Windows). Anywhere else, or when input/output is
redirected, every menu falls back to typing a number.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
from dataclasses import dataclass

IS_WIN = os.name == "nt"
if IS_WIN:
    import msvcrt

COLOR = False  # ANSI colors / cursor movement available
INTERACTIVE = False  # single-key input (arrow keys) available


def _enable_vt() -> bool:
    """Turn on ANSI escape processing in the Windows console."""
    if not IS_WIN:
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def init() -> None:
    global COLOR, INTERACTIVE
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ and _enable_vt()
    INTERACTIVE = COLOR and IS_WIN and sys.stdin.isatty()
    atexit.register(show_cursor)


# --- colors ---------------------------------------------------------------


def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GOLD = rgb(255, 209, 102)
AMBER = rgb(255, 160, 60)
GREEN = rgb(110, 220, 120)
RED = rgb(255, 95, 95)
YELLOW = rgb(255, 220, 90)
CYAN = rgb(110, 200, 255)
GREY = rgb(150, 150, 160)

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def c(text: str, *styles: str) -> str:
    return f"{''.join(styles)}{text}{RESET}" if COLOR and styles else text


def visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


def out(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def ok(msg: str) -> None:
    out(f"  {c('✓', GREEN, BOLD)} {msg}")


def warn(msg: str) -> None:
    out(f"  {c('!', YELLOW, BOLD)} {msg}")


def err(msg: str) -> None:
    out(f"  {c('✗', RED, BOLD)} {msg}")


def hide_cursor() -> None:
    if COLOR:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()


def show_cursor() -> None:
    if COLOR:
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()


def clear() -> None:
    if COLOR:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()
    else:
        out()


def term_width() -> int:
    return shutil.get_terminal_size((100, 30)).columns


def rule(width: int | None = None) -> None:
    out("  " + c("─" * ((width or min(term_width(), 92)) - 4), DIM))


# --- banner ---------------------------------------------------------------

# "ANSI Shadow" letters, 6 rows each.
_GLYPHS = {
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "X": ["██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝"],
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "F": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "██║     ", "╚═╝     "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "G": [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    " ": ["   "] * 6,
}

# Forge gradient: gold -> orange -> ember red.
_GRADIENT = [(255, 221, 110), (255, 170, 60), (240, 95, 45), (190, 40, 40)]


def _gradient(t: float) -> tuple[int, int, int]:
    t = min(max(t, 0.0), 1.0) * (len(_GRADIENT) - 1)
    i = min(int(t), len(_GRADIENT) - 2)
    f = t - i
    a, b = _GRADIENT[i], _GRADIENT[i + 1]
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))  # type: ignore[return-value]


def _big_text(text: str) -> list[str]:
    return ["".join(_GLYPHS[ch][row] for ch in text) for row in range(6)]


def banner(version: str) -> None:
    rows = _big_text("RXP REFORGE")
    width = len(rows[0])
    tagline = "Re-forge your RestedXP guides for every BattleTag"
    signature = f"⚔  made by SirRadi  ·  v{version}"

    out()
    if term_width() < width + 4:
        # Narrow terminal: compact header.
        out("  " + c("⚔  RXP REFORGE  ⚔", GOLD, BOLD))
        out("  " + c(tagline, GREY))
        out("  " + c(signature, AMBER, BOLD))
        out()
        return

    for row in rows:
        if COLOR:
            line = "".join(
                rgb(*_gradient(x / (width - 1))) + ch if ch != " " else ch
                for x, ch in enumerate(row)
            )
            out("  " + line + RESET)
        else:
            out("  " + row)
    gap = width - len(tagline) - len(signature)
    out("  " + c(tagline, GREY) + " " * max(gap, 2) + c(signature, AMBER, BOLD))
    out()


# --- keys -----------------------------------------------------------------

UP, DOWN, LEFT, RIGHT = "UP", "DOWN", "LEFT", "RIGHT"
HOME, END = "HOME", "END"
ENTER, ESC, SPACE, BACKSPACE = "ENTER", "ESC", "SPACE", "BACKSPACE"


def read_key() -> str:
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return {"H": UP, "P": DOWN, "K": LEFT, "M": RIGHT, "G": HOME, "O": END}.get(code, "")
    if ch == "\x03":
        raise KeyboardInterrupt
    return {"\r": ENTER, "\n": ENTER, "\x1b": ESC, " ": SPACE, "\x08": BACKSPACE}.get(ch, ch)


class _Live:
    """Redraws a block of lines in place (no flicker, no scrolling)."""

    def __init__(self) -> None:
        self.lines = 0

    def draw(self, lines: list[str]) -> None:
        prefix = f"\x1b[{self.lines}A\r\x1b[J" if self.lines else ""
        sys.stdout.write(prefix + "\n".join(lines) + "\n")
        sys.stdout.flush()
        self.lines = len(lines)


def _hint(text: str) -> str:
    return "  " + c(text, DIM)


# --- widgets --------------------------------------------------------------


@dataclass
class Item:
    key: str  # hotkey, also returned when chosen
    label: str
    hint: str = ""
    style: str = ""


def select(items: list[Item], default: int = 0, back_label: str = "back") -> str | None:
    """Menu with a cursor. Returns the chosen item's key, or None on Esc."""
    if not INTERACTIVE:
        return _select_typed(items)

    cursor = min(max(default, 0), len(items) - 1)
    label_w = max(visible_len(i.label) for i in items) + 3
    live = _Live()
    hide_cursor()
    try:
        while True:
            lines = []
            for idx, item in enumerate(items):
                key = c(item.key, GREY) if item.key else " "
                hint = c(item.hint, GREY) if item.hint else ""
                if idx == cursor:
                    label = c(item.label, item.style or GOLD, BOLD)
                    lines.append(f"  {c('▸', GOLD, BOLD)} {key}  {pad(label, label_w)}{hint}")
                else:
                    label = c(item.label, item.style) if item.style else item.label
                    lines.append(f"    {key}  {pad(label, label_w)}{hint}")
            lines.append("")
            lines.append(_hint(f"↑↓ move · Enter select · number = shortcut · Esc {back_label}"))
            live.draw(lines)

            key = read_key()
            if key == UP:
                cursor = (cursor - 1) % len(items)
            elif key == DOWN:
                cursor = (cursor + 1) % len(items)
            elif key == HOME:
                cursor = 0
            elif key == END:
                cursor = len(items) - 1
            elif key == ENTER:
                return items[cursor].key
            elif key == ESC:
                return None
            else:
                for item in items:
                    if item.key and key.lower() == item.key.lower():
                        return item.key
    finally:
        show_cursor()


def _select_typed(items: list[Item]) -> str | None:
    label_w = max(visible_len(i.label) for i in items) + 3
    for item in items:
        out(f"    {item.key}  {pad(item.label, label_w)}{item.hint}")
    out()
    keys = {i.key.lower(): i.key for i in items}
    while True:
        try:
            answer = input("  > ").strip().lower()
        except EOFError:
            return None
        if not answer:
            return None
        if answer in keys:
            return keys[answer]
        warn("Please type one of the numbers above.")


def parse_selection(text: str, count: int) -> set[int] | None:
    """'1,3,5' / '2-4' / 'y' / 'all' -> 0-based indices. None if invalid."""
    text = text.strip().lower()
    if text in ("y", "a", "all", "*"):
        return set(range(count))
    if text in ("n", "none"):
        return set()
    picked: set[int] = set()
    for token in re.split(r"[,\s]+", text):
        if not token:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", token)
        if not m:
            return None
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        if lo > hi:
            lo, hi = hi, lo
        if lo < 1 or hi > count:
            return None
        picked.update(range(lo - 1, hi))
    return picked


def checklist(labels: list[str], checked: set[int]) -> set[int] | None:
    """Multi-select list. Returns the checked indices, or None on Esc."""
    if not INTERACTIVE:
        return _checklist_typed(labels, checked)

    checked = set(checked)
    cursor = 0
    typed = ""
    error = ""
    live = _Live()
    hide_cursor()
    try:
        while True:
            lines = []
            for idx, label in enumerate(labels):
                box = c("[x]", GREEN, BOLD) if idx in checked else c("[ ]", GREY)
                num = c(f"{idx + 1:>2}", GREY)
                text = c(label, GOLD, BOLD) if idx == cursor else label
                arrow = c("▸", GOLD, BOLD) if idx == cursor else " "
                lines.append(f"  {arrow} {box} {num}  {text}")
            lines.append("")
            lines.append(f"  {c(f'{len(checked)}/{len(labels)} selected', CYAN)}")
            if typed:
                lines.append(f"  Selection: {c(typed, GOLD, BOLD)}{c('_', GOLD)}   {c('Enter = apply', DIM)}")
            elif error:
                lines.append(f"  {c(error, RED)}")
            else:
                lines.append("")
            lines.append(_hint("↑↓ move · Space toggle · Y all · N none · type 1,3,5 or 2-4"))
            lines.append(_hint("Enter confirm · Esc cancel"))
            live.draw(lines)

            key = read_key()
            error = ""
            if key == UP:
                cursor = (cursor - 1) % len(labels)
            elif key == DOWN:
                cursor = (cursor + 1) % len(labels)
            elif key == SPACE:
                checked ^= {cursor}
            elif key == ESC:
                if typed:
                    typed = ""
                else:
                    return None
            elif key == BACKSPACE:
                typed = typed[:-1]
            elif key == ENTER:
                if not typed:
                    return checked
                picked = parse_selection(typed, len(labels))
                if picked is None:
                    error = f"'{typed}' is not valid — use numbers 1-{len(labels)}, e.g. 1,3,5 or 2-4"
                else:
                    checked = picked
                typed = ""
            elif key.lower() in ("y", "a") and not typed:
                checked = set(range(len(labels)))
            elif key.lower() == "n" and not typed:
                checked = set()
            elif len(key) == 1 and (key.isdigit() or key in ",- "):
                typed += key
    finally:
        show_cursor()


def _checklist_typed(labels: list[str], checked: set[int]) -> set[int] | None:
    for idx, label in enumerate(labels):
        mark = "x" if idx in checked else " "
        out(f"    [{mark}] {idx + 1:>2}  {label}")
    out()
    while True:
        try:
            answer = input("  Select (e.g. 1,3,5 / 2-4 / Y = all, Enter = keep): ").strip()
        except EOFError:
            return None
        if not answer:
            return set(checked)
        picked = parse_selection(answer, len(labels))
        if picked is not None:
            return picked
        warn(f"Use numbers 1-{len(labels)}, e.g. 1,3,5 or 2-4, or Y for all.")


def prompt(label: str) -> str:
    """Free text input. Empty string means cancel."""
    show_cursor()
    try:
        return input(f"  {c('›', GOLD, BOLD)} {label}").strip()
    except EOFError:
        return ""


def confirm(question: str, default: bool = True) -> bool:
    choices = "Y/n" if default else "y/N"
    sys.stdout.write(f"  {c('?', CYAN, BOLD)} {question} {c(f'[{choices}]', GREY)} ")
    sys.stdout.flush()
    if not INTERACTIVE:
        try:
            answer = input().strip().lower()
        except EOFError:
            return default
        return default if not answer else answer.startswith("y")
    while True:
        key = read_key()
        if key == ENTER:
            answer = default
        elif key == ESC:
            answer = False
        elif key.lower() in ("y", "j"):
            answer = True
        elif key.lower() == "n":
            answer = False
        else:
            continue
        out(c("yes", GREEN) if answer else c("no", GREY))
        return answer


def wait_key(msg: str = "Press any key to go back…") -> None:
    out()
    if not INTERACTIVE:
        try:
            input(f"  {c(msg.replace('any key', 'Enter'), DIM)}")
        except EOFError:
            pass
        return
    sys.stdout.write(f"  {c(msg, DIM)}")
    sys.stdout.flush()
    hide_cursor()
    read_key()
    show_cursor()
    out()


def progress(done: int, total: int, label: str = "", width: int = 32) -> None:
    """Single-line progress bar, redrawn in place."""
    frac = done / total if total else 1.0
    filled = round(frac * width)
    bar = c("█" * filled, AMBER) + c("░" * (width - filled), DIM)
    line = f"  {bar}  {c(f'{frac:>4.0%}', GOLD, BOLD)}  {c(label, GREY)}"
    if COLOR:
        sys.stdout.write("\r\x1b[K" + line)
        if done >= total:
            sys.stdout.write("\n")
        sys.stdout.flush()
    elif done >= total:
        out(line)
