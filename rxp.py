#!/usr/bin/env python3
"""RXP Reforge — re-forge your RestedXP guides for all your BattleTags.

made by SirRadi

  rxp                      interactive menu
  rxp Name#1234 ...        forge all guides for these BattleTags
  rxp run                  forge with the BattleTags/guides saved in the menu
  rxp list                 show the guides in the source folder
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# The portable runtime (embeddable Python) doesn't put the script folder on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reforge import __version__, tui  # noqa: E402
from reforge.guides import (
    ROOT,
    Config,
    ReforgeResult,
    Source,
    forged_files,
    is_battletag,
    load_config,
    reforge,
    resolve,
    save_config,
    scan_sources,
    select_sources,
)
from reforge.tui import AMBER, BOLD, CYAN, DIM, GOLD, GREY, RED, YELLOW, Item, c


# --- shared helpers -------------------------------------------------------


def short_path(path: Path) -> str:
    """Show paths inside the project relative to it."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def human_size(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


def tag_from_folder(name: str) -> str:
    """Output folder name back to a BattleTag: Name_1234 -> Name#1234."""
    head, _, num = name.rpartition("_")
    return f"{head}#{num}" if head and num.isdigit() else name


def load_counts(sources: list[Source]) -> None:
    """Decrypt all sources once (cached), with a progress bar."""
    todo = [s for s in sources if s._decrypted is None]
    for i, src in enumerate(todo, 1):
        tui.progress(i - 1, len(todo), f"reading {src.name}…")
        try:
            src.decrypt()
        except Exception:
            pass  # shown as unreadable
        tui.progress(i, len(todo), "guides loaded" if i == len(todo) else f"reading {src.name}…")


def guide_count(src: Source) -> int | None:
    try:
        return src.decrypt().guide_count
    except Exception:
        return None


def run_reforge(sources: list[Source], tags: list[str], out_dir: Path) -> list[ReforgeResult]:
    results = reforge(sources, tags, out_dir, on_step=lambda d, t, label: tui.progress(d, t, label))
    tui.out()
    for tag in tags:
        mine = [r for r in results if r.battletag == tag]
        good = [r for r in mine if r.ok]
        folder = short_path(good[0].output.parent) if good and good[0].output else ""
        line = f"{c(tag, GOLD, BOLD)}  {len(good)}/{len(mine)} guides"
        if folder:
            line += c(f"  →  {folder}", GREY)
        (tui.ok if len(good) == len(mine) else tui.err)(line)
        for r in mine:
            if not r.ok:
                tui.out(f"      {c(r.source.name, RED)}: {r.error}")
    return results


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=False)


def copy_to_clipboard(text: str) -> bool:
    if os.name == "nt":
        cmd = ["clip"]
    elif sys.platform == "darwin":
        cmd = ["pbcopy"]
    else:
        cmd = ["xclip", "-selection", "clipboard"]
    try:
        subprocess.run(cmd, input=text.encode("utf-8"), check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


# --- interactive menu -----------------------------------------------------


class App:
    def __init__(self) -> None:
        self.cfg: Config = load_config()
        self.sources: list[Source] = []
        self.flash: list[tuple[str, str]] = []  # (kind, text) shown on the next main screen
        self.rescan()

    # -- state --

    def rescan(self) -> None:
        self.sources = scan_sources(self.cfg.source_path)

    def save(self) -> None:
        save_config(self.cfg)

    def selected(self) -> list[Source]:
        return select_sources(self.sources, self.cfg.selected)

    def note(self, kind: str, text: str) -> None:
        self.flash.append((kind, text))

    # -- screens --

    def screen(self, title: str | None = None) -> None:
        tui.clear()
        tui.banner(__version__)
        if title:
            tui.out(f"  {c('»', AMBER, BOLD)} {c(title, GOLD, BOLD)}")
            tui.rule()

    def status(self) -> None:
        src = self.cfg.source_path
        if not src.is_dir():
            src_info = c("folder not found — change it in Settings", RED)
        elif not self.sources:
            src_info = c("no guide files found", YELLOW)
        else:
            src_info = c(f"{len(self.sources)} guides found", GREY)

        tags = self.cfg.battletags
        if tags:
            shown = ", ".join(c(t, GOLD) for t in tags[:3])
            tag_info = shown + (c(f"  +{len(tags) - 3} more", GREY) if len(tags) > 3 else "")
        else:
            tag_info = c("none yet — add one with [1]", YELLOW)

        n_sel = len(self.selected())
        sel_info = f"{n_sel}/{len(self.sources)} selected"
        if self.cfg.selected is None and self.sources:
            sel_info += c("  (all)", GREY)

        rows = [
            ("Source", f"{short_path(src)}   {src_info}"),
            ("BattleTags", tag_info),
            ("Guides", sel_info),
            ("Output", short_path(self.cfg.output_path)),
        ]
        tui.rule()
        for label, value in rows:
            tui.out(f"  {c(f'{label:<11}', CYAN)} {value}")
        tui.rule()

        for kind, text in self.flash:
            {"ok": tui.ok, "warn": tui.warn, "err": tui.err}[kind](text)
        if self.flash:
            tui.out()
        self.flash.clear()

    def run(self) -> None:
        actions = {
            "1": self.battletags_menu,
            "2": self.select_guides,
            "3": self.do_reforge,
            "4": self.copy_guide,
            "5": self.source_overview,
            "6": self.settings,
            "7": self.open_output,
        }
        while True:
            self.screen()
            self.status()
            tags = len(self.cfg.battletags)
            items = [
                Item("1", "Enter BattleTag(s)", f"{tags} saved" if tags else "start here"),
                Item("2", "Select Guides", f"{len(self.selected())}/{len(self.sources)}"),
                Item("3", "⚔  Reforge!", "forge guides for your BattleTags", AMBER),
                Item("4", "Copy guide to clipboard", "paste in-game with Ctrl+V"),
                Item("5", "Source overview"),
                Item("6", "Settings"),
                Item("7", "Open output folder"),
                Item("0", "Exit"),
            ]
            default = 2 if tags else 0
            choice = tui.select(items, default=default, back_label="exit")
            if choice in (None, "0"):
                break
            actions[choice]()

        tui.clear()
        tui.out()
        tui.out(f"  {c('⚔', AMBER, BOLD)}  {c('May your XP be rested.', GOLD, BOLD)}  {c('— SirRadi', GREY)}")
        tui.out()

    # 1 -- BattleTags

    def battletags_menu(self) -> None:
        while True:
            self.screen("BattleTags — the accounts you forge guides for")
            if self.cfg.battletags:
                for i, tag in enumerate(self.cfg.battletags, 1):
                    tui.out(f"    {c(f'{i:>2}', GREY)}  {c(tag, GOLD)}")
            else:
                tui.out(c("    No BattleTags yet.", YELLOW))
            tui.out()

            items = [Item("1", "Add BattleTag(s)")]
            if self.cfg.battletags:
                items += [Item("2", "Remove BattleTag(s)"), Item("3", "Remove all")]
            items.append(Item("0", "Back"))

            choice = tui.select(items)
            if choice in (None, "0"):
                return
            if choice == "1":
                self.add_battletags()
            elif choice == "2":
                tui.out()
                picked = tui.checklist(self.cfg.battletags, set())
                if picked:
                    removed = [t for i, t in enumerate(self.cfg.battletags) if i in picked]
                    self.cfg.battletags = [t for t in self.cfg.battletags if t not in removed]
                    self.save()
                    self.note("ok", f"Removed {', '.join(removed)}")
            elif choice == "3":
                tui.out()
                if tui.confirm("Remove all BattleTags?", default=False):
                    self.cfg.battletags = []
                    self.save()

    def add_battletags(self) -> bool:
        tui.out()
        tui.out(c("    Format: Name#1234 — several at once with commas, Enter alone cancels.", GREY))
        raw = tui.prompt("BattleTag(s): ")
        if not raw:
            return False
        added, invalid = self.cfg.add_battletags([t for t in re.split(r"[,;\s]+", raw) if t])
        if added:
            self.save()
            tui.ok(f"Added {', '.join(c(t, GOLD) for t in added)}")
            self.note("ok", f"Added {', '.join(added)}")
        if invalid:
            tui.err(f"Not a BattleTag: {', '.join(invalid)}  {c('(format Name#1234)', GREY)}")
        if not added and not invalid:
            tui.warn("Already saved.")
        if invalid or not added:
            tui.wait_key()
        return bool(added)

    # 2 -- guides

    def select_guides(self) -> None:
        if not self.require_sources():
            return
        self.screen("Select Guides")
        load_counts(self.sources)
        tui.out()

        labels = []
        for src in self.sources:
            n = guide_count(src)
            count = c(f"{n:>4} guides", GREY) if n is not None else c("unreadable", RED)
            labels.append(f"{src.name:<12} {count}")
        selected = {s.name for s in self.selected()}
        current = {i for i, s in enumerate(self.sources) if s.name in selected}

        picked = tui.checklist(labels, current)
        if picked is None:
            return
        if not picked:
            self.note("warn", "No guide selected — kept the previous selection.")
            return
        if len(picked) == len(self.sources):
            self.cfg.selected = None
        else:
            self.cfg.selected = [self.sources[i].name for i in sorted(picked)]
        self.save()
        self.note("ok", f"{len(picked)}/{len(self.sources)} guides selected")

    # 3 -- reforge

    def do_reforge(self) -> None:
        if not self.require_sources():
            return
        if not self.cfg.battletags:
            self.screen("Reforge!")
            tui.warn("You need at least one BattleTag first.")
            if not self.add_battletags():
                return

        chosen = self.selected()
        if not chosen:
            self.note("warn", "No guides selected — pick some with [2].")
            return
        tags = self.cfg.battletags
        out_dir = self.cfg.output_path

        self.screen("Reforge!")
        tui.out(f"  {c('Guides', CYAN)}      {', '.join(s.name for s in chosen)}")
        tui.out(f"  {c('BattleTags', CYAN)}  {', '.join(c(t, GOLD) for t in tags)}")
        total = len(chosen) * len(tags)
        tui.out(f"  {c('Result', CYAN)}      {c(str(total), BOLD)} files → {short_path(out_dir)}")
        tui.out()
        if not tui.confirm("Start forging?"):
            return
        tui.out()

        results = run_reforge(chosen, tags, out_dir)
        tui.out()
        failed = sum(not r.ok for r in results)
        if failed:
            self.note("err", f"{failed} file(s) failed — see Source overview")
        else:
            self.note("ok", f"Forged {len(results)} files for {len(tags)} BattleTag(s)")
        if tui.confirm("Open output folder?"):
            open_folder(out_dir)

    # 4 -- clipboard

    def copy_guide(self) -> None:
        forged = forged_files(self.cfg.output_path)
        if not forged:
            self.note("warn", "Nothing forged yet — use [3] Reforge! first.")
            return

        self.screen("Copy guide to clipboard — pick a BattleTag")
        folders = list(forged)
        items = [Item(str(i), tag_from_folder(f), f"{len(forged[f])} guides") for i, f in enumerate(folders, 1)]
        choice = tui.select(items + [Item("0", "Back")])
        if choice in (None, "0"):
            return
        folder = folders[int(choice) - 1]
        tag = tag_from_folder(folder)

        self.screen(f"Copy guide to clipboard — {tag}")
        files = forged[folder]
        items = [
            Item(str(i), p.name.split("_guide_")[0], human_size(p.stat().st_size))
            for i, p in enumerate(files, 1)
        ]
        choice = tui.select(items + [Item("0", "Back")])
        if choice in (None, "0"):
            return
        path = files[int(choice) - 1]
        guide = path.name.split("_guide_")[0]

        if copy_to_clipboard(path.read_text("utf-8")):
            self.note("ok", f"Copied {guide} for {tag} — paste it in-game into the RXP import window with Ctrl+V")
        else:
            self.note("err", f"Clipboard not available — open the file instead: {short_path(path)}")

    # 5 -- overview

    def source_overview(self) -> None:
        if not self.require_sources():
            return
        self.screen("Source overview")
        print_overview(self.sources, self.cfg.source_path)
        tui.wait_key()

    # 6 -- settings

    def settings(self) -> None:
        while True:
            self.screen("Settings")
            items = [
                Item("1", "Source folder", short_path(self.cfg.source_path)),
                Item("2", "Output folder", short_path(self.cfg.output_path)),
                Item("3", "Reset to defaults", "source_guides / output"),
                Item("0", "Back"),
            ]
            choice = tui.select(items)
            if choice in (None, "0"):
                return
            if choice == "3":
                defaults = Config()
                self.cfg.source_dir, self.cfg.output_dir = defaults.source_dir, defaults.output_dir
            else:
                tui.out()
                tui.out(c("    Relative paths start in the project folder. Enter alone keeps the current one.", GREY))
                raw = tui.prompt("New folder: ").strip('"')
                if not raw:
                    continue
                if choice == "1":
                    if not resolve(raw).is_dir():
                        tui.err(f"Folder not found: {raw}")
                        tui.wait_key()
                        continue
                    self.cfg.source_dir = raw
                else:
                    self.cfg.output_dir = raw
            self.save()
            self.rescan()

    # 7 -- output

    def open_output(self) -> None:
        open_folder(self.cfg.output_path)
        self.note("ok", f"Opened {short_path(self.cfg.output_path)}")

    # -- guards --

    def require_sources(self) -> bool:
        if self.sources:
            return True
        self.note(
            "err",
            f"No guide files in {short_path(self.cfg.source_path)} — "
            "put your <guide>_guide_<Name>_<Number>.txt files there.",
        )
        return False


def print_overview(sources: list[Source], src_dir: Path) -> None:
    tui.out(c(f"  {short_path(src_dir)}", GREY))
    tui.out()
    load_counts(sources)
    tui.out()
    tui.out(c(f"    {'#':>2}  {'Guide':<12} {'Guides':>6}   {'Source BattleTag':<20} {'Size':>8}", CYAN))
    total = 0
    for i, src in enumerate(sources, 1):
        n = guide_count(src)
        total += n or 0
        count = f"{n:>6}" if n is not None else c("  error", RED)
        tui.out(f"    {i:>2}  {c(f'{src.name:<12}', GOLD)} {count}   {src.source_tag:<20} {human_size(src.size):>8}")
    tui.out(c(f"    {'':>2}  {'total':<12} {total:>6}", DIM))


# --- direct mode ----------------------------------------------------------


def direct(args: argparse.Namespace) -> int:
    cfg = load_config()
    src_dir = resolve(args.src) if args.src else cfg.source_path
    out_dir = resolve(args.out) if args.out else cfg.output_path
    sources = scan_sources(src_dir)
    if not sources:
        tui.err(f"No *_guide_<Name>_<Number>.txt files in {src_dir}")
        return 1

    if args.targets == ["list"]:
        print_overview(sources, src_dir)
        return 0

    if args.targets == ["run"]:
        tags = cfg.battletags
        if not tags:
            tui.err("No saved BattleTags — add some in the menu (rxp) or pass them: rxp Name#1234")
            return 1
        chosen = select_sources(sources, cfg.selected)
    else:
        tags = args.targets
        bad = [t for t in tags if not is_battletag(t)]
        if bad:
            tui.err(f"Not a BattleTag: {', '.join(bad)}  (format Name#1234)")
            return 1
        chosen = sources

    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        chosen = select_sources(chosen, wanted)
        if not chosen:
            tui.err(f"None of these guides found: {args.only}")
            return 1

    tui.out(f"  {c('⚔', AMBER, BOLD)} {c('RXP Reforge', GOLD, BOLD)} {c(f'v{__version__} · made by SirRadi', GREY)}")
    tui.out(f"  {len(chosen)} guides × {len(tags)} BattleTag(s) → {short_path(out_dir)}")
    tui.out()
    results = run_reforge(chosen, tags, out_dir)
    return 0 if all(r.ok for r in results) else 1


def main() -> int:
    tui.init()
    parser = argparse.ArgumentParser(
        prog="rxp",
        description="RXP Reforge — re-forge your RestedXP guides for all your BattleTags. made by SirRadi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  rxp                                  open the menu\n"
            '  rxp "Schattenwolf#2234"              forge all guides for one BattleTag\n'
            '  rxp "Tag#1111" "Tag#2222" --only mop,tbc\n'
            "  rxp run                              use BattleTags + guides saved in the menu\n"
            "  rxp list                             show source guides"
        ),
    )
    parser.add_argument("targets", nargs="*", metavar="BATTLETAG", help='BattleTag(s) like "Name#1234", or "run" / "list"')
    parser.add_argument("--only", metavar="GUIDES", help="only these guides, e.g. mop,tbc")
    parser.add_argument("--src", metavar="DIR", help="source folder (default: source_guides)")
    parser.add_argument("--out", metavar="DIR", help="output folder (default: output)")
    parser.add_argument("--version", action="version", version=f"RXP Reforge v{__version__} — made by SirRadi")
    args = parser.parse_args()

    try:
        if not args.targets and not (args.only or args.src or args.out):
            App().run()
            return 0
        if not args.targets:
            parser.error("give BattleTag(s), 'run' or 'list'")
        return direct(args)
    except KeyboardInterrupt:
        tui.show_cursor()
        tui.out()
        tui.out(c("  Cancelled.", GREY))
        return 130


if __name__ == "__main__":
    sys.exit(main())
