# spyc is a terminal viewer for browsing code bases.
# Copyright © 2026 Adam Waldenberg, Adeptum AB, Org.nr 559494-1824.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Website: https://www.adeptum.se
# Contact: info@adeptum.se


from dataclasses import dataclass
from pathlib import Path

from rich.text import Text

from spyc.core.file_index import MAX_INDEXED_FILES, FileIndex
from spyc.core.languages import detect_language
from spyc.core.printable import printable
from spyc.core.project import KeyFile, detect_build_systems, key_files
from spyc.core.source import DiskSource, FileSource

STAT_LIMIT = 50_000
README_LINES = 40
README_BYTES = 8192
README_FILE_LIMIT = 1024 * 1024
BAR_WIDTH = 20
LANGUAGES_SHOWN = 8


@dataclass(frozen=True)
class LanguageShare:
    name: str
    files: int
    size: int
    percent: float


@dataclass(frozen=True)
class Overview:
    name: str
    root: Path
    file_count: int
    truncated: bool
    sampled: bool
    build_systems: tuple[str, ...]
    languages: tuple[LanguageShare, ...]
    key_files: tuple[KeyFile, ...]
    readme: str | None


# Sizing every file of a huge tree would stall the start-up for seconds, so
# the shares are measured on the first STAT_LIMIT files and marked as sampled.
def build_overview(index: FileIndex, source: FileSource | None = None) -> Overview:
    source = source or DiskSource(index.root)
    totals: dict[str, list[int]] = {}
    for path in index.paths[:STAT_LIMIT]:
        language = detect_language(path)
        stamp = None if language is None else source.stamp(path)
        if stamp is None:
            continue
        entry = totals.setdefault(language.name, [0, 0])
        entry[0] += 1
        entry[1] += stamp.size
    everything = sum(size for _, size in totals.values())
    shares = (LanguageShare(name, files, size, round(100 * size / everything, 1) if everything else 0.0)
              for name, (files, size) in totals.items())
    keys = key_files(index.paths)
    return Overview(index.root.name, index.root, len(index.paths), index.truncated, len(index.paths) > STAT_LIMIT,
                    tuple(detect_build_systems(index.paths)),
                    tuple(sorted(shares, key=lambda share: (-share.size, share.name))), tuple(keys),
                    _readme(source, keys))


def _readme(source: FileSource, keys: list[KeyFile]) -> str | None:
    name = next((key.path for key in keys if key.kind == "Readme" and "/" not in key.path), None)
    data = None if name is None else source.read(name, README_FILE_LIMIT)
    if data is None:
        return None
    text = printable(data[:README_BYTES].decode("utf-8", errors="replace"), keep_newlines=True)
    return "\n".join(text.splitlines()[:README_LINES])


def summary_text(overview: Overview) -> Text:
    text = Text()
    text.append(f"{printable(overview.name)}\n", style="bold")
    text.append(f"{printable(str(overview.root))}\n", style="dim")
    noun = "file" if overview.file_count == 1 else "files"
    text.append(" · ".join([f"{overview.file_count:,} {noun}", *overview.build_systems]) + "\n")
    if overview.truncated:
        text.append(f"The file list is capped at {MAX_INDEXED_FILES:,} files.\n", style="yellow")
    if overview.sampled:
        text.append(f"Languages are measured on the first {STAT_LIMIT:,} files.\n", style="dim")
    text.append("\n")
    for share in overview.languages[:LANGUAGES_SHOWN]:
        filled = round(BAR_WIDTH * share.percent / 100)
        text.append(f"{share.name:<14}")
        text.append("█" * filled, style="green")
        text.append("░" * (BAR_WIDTH - filled), style="dim")
        text.append(f" {share.percent:5.1f}%  {share.files:,} files\n")
    return text
