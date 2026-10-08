"""Source scanning, config and the actual re-encrypt job."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .crypto import DecryptResult, decrypt_guide_file, encrypt_for_battletag

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

# <guide>_guide_<Name>_<Number>.txt — duplicates like "x (1).txt" don't match.
FILE_RE = re.compile(r"^(.+?)_guide_(.+)_(\d+)\.txt$", re.IGNORECASE)
BATTLETAG_RE = re.compile(r"^[^#\s]+#\d+$")
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')


def is_battletag(tag: str) -> bool:
    return bool(BATTLETAG_RE.match(tag))


def safe_tag(tag: str) -> str:
    """BattleTag as used in folder/file names: Name#1234 -> Name_1234."""
    return _UNSAFE_CHARS.sub("", tag.replace("#", "_"))


def resolve(path: str) -> Path:
    """Relative paths are relative to the project folder, so the tool stays portable."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else ROOT / p


# --- config ---------------------------------------------------------------


@dataclass
class Config:
    source_dir: str = "source_guides"
    output_dir: str = "output"
    battletags: list[str] = field(default_factory=list)
    selected: list[str] | None = None  # None = all guides (incl. ones added later)

    @property
    def source_path(self) -> Path:
        return resolve(self.source_dir)

    @property
    def output_path(self) -> Path:
        return resolve(self.output_dir)

    def add_battletags(self, tags: list[str]) -> tuple[list[str], list[str]]:
        """Add tags, skipping duplicates (case-insensitive). Returns (added, invalid)."""
        known = {t.lower() for t in self.battletags}
        added, invalid = [], []
        for tag in tags:
            if not is_battletag(tag):
                invalid.append(tag)
            elif tag.lower() not in known:
                self.battletags.append(tag)
                known.add(tag.lower())
                added.append(tag)
        return added, invalid


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    try:
        data = json.loads(CONFIG_PATH.read_text("utf-8"))
        defaults = asdict(Config())
        return Config(**{k: data.get(k, v) for k, v in defaults.items()})
    except (ValueError, TypeError):
        return Config()


def save_config(cfg: Config) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), "utf-8")


# --- sources --------------------------------------------------------------


@dataclass(eq=False)
class Source:
    path: Path
    name: str
    source_tag: str
    _decrypted: DecryptResult | None = field(default=None, repr=False)

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    def decrypt(self) -> DecryptResult:
        """Decrypt once, then keep the result for the rest of the session."""
        if self._decrypted is None:
            self._decrypted = decrypt_guide_file(self.path.read_text("utf-8"), self.source_tag)
        return self._decrypted


def scan_sources(src_dir: Path) -> list[Source]:
    if not src_dir.is_dir():
        return []
    sources = []
    for path in sorted(src_dir.iterdir()):
        m = FILE_RE.match(path.name)
        if m and path.is_file():
            name, tag_name, tag_num = m.groups()
            sources.append(Source(path, name, f"{tag_name}#{tag_num}"))
    return sources


def select_sources(sources: list[Source], selected: list[str] | None) -> list[Source]:
    if selected is None:
        return sources
    wanted = {s.lower() for s in selected}
    return [s for s in sources if s.name.lower() in wanted]


# --- reforge --------------------------------------------------------------


@dataclass
class ReforgeResult:
    source: Source
    battletag: str
    output: Path | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def reforge(
    sources: list[Source],
    battletags: list[str],
    out_dir: Path,
    on_step: Callable[[int, int, str], None] | None = None,
    on_result: Callable[[ReforgeResult], None] | None = None,
) -> list[ReforgeResult]:
    """Re-encrypt every source for every BattleTag into out_dir/<Tag>/.

    on_step(done, total, label) is called for progress, on_result for each file.
    """
    total = len(sources) * (1 + len(battletags))
    done = 0
    results: list[ReforgeResult] = []

    def step(label: str) -> None:
        nonlocal done
        done += 1
        if on_step:
            on_step(done, total, label)

    def emit(result: ReforgeResult) -> None:
        results.append(result)
        if on_result:
            on_result(result)

    for src in sources:
        try:
            dec = src.decrypt()
        except Exception as e:  # wrong source tag, corrupt file, ...
            step(f"{src.name}: read failed")
            for tag in battletags:
                step(f"{src.name} → {tag}")
                emit(ReforgeResult(src, tag, error=f"cannot decrypt with {src.source_tag} ({e})"))
            continue
        step(f"{src.name}: decrypted")

        for tag in battletags:
            encrypted = encrypt_for_battletag(dec.plaintext, tag, dec.version)
            # Cross-check: the new file must decrypt with the target tag.
            if decrypt_guide_file(encrypted, tag).guide_count != dec.guide_count:
                emit(ReforgeResult(src, tag, error="verification failed"))
            else:
                folder = out_dir / safe_tag(tag)
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"{src.name}_guide_{safe_tag(tag)}.txt"
                path.write_text(encrypted, "utf-8")
                emit(ReforgeResult(src, tag, output=path))
            step(f"{src.name} → {tag}")

    return results


def forged_files(out_dir: Path) -> dict[str, list[Path]]:
    """Existing output: {tag folder name: [guide files]}."""
    if not out_dir.is_dir():
        return {}
    found = {}
    for folder in sorted(out_dir.iterdir()):
        if folder.is_dir():
            files = sorted(p for p in folder.glob("*_guide_*.txt") if p.is_file())
            if files:
                found[folder.name] = files
    return found
