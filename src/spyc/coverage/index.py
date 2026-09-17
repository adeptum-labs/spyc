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


import posixpath
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from spyc.coverage.model import Lines, counts, merge_lines
from spyc.coverage.reports import LoadedReport
from spyc.coverage.resolve import PathResolver

STALE_GRACE = 1.0


def _percent(covered_and_total: tuple[int, int]) -> float | None:
    covered, total = covered_and_total
    return 100 * covered / total if total else None


# The coverage of the files of a project: what its reports say, merged, with
# the share of the lines that ran for every file and directory.
@dataclass
class Coverage:
    files: dict[str, Lines] = field(default_factory=dict)
    formats: tuple[str, ...] = ()
    unmatched: int = 0
    _oldest: dict[str, float] = field(default_factory=dict)
    _file_counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    _directories: dict[str, tuple[int, int]] = field(default_factory=dict)

    @classmethod
    def build(cls, root: Path, paths: Sequence[str], reports: Sequence[LoadedReport]) -> "Coverage":
        resolver, coverage = PathResolver(root, paths), cls()
        formats: list[str] = []
        for loaded in reports:
            formats.append(loaded.report.format)
            coverage._add(resolver, root, loaded)
        coverage.formats = tuple(dict.fromkeys(formats))
        coverage._roll_up()
        return coverage

    def lines_of(self, path: str) -> Lines | None:
        return self.files.get(path)

    def file_percent(self, path: str) -> float | None:
        return _percent(self._file_counts[path]) if path in self._file_counts else None

    def directory_percent(self, directory: str) -> float | None:
        return _percent(self._directories.get(directory, (0, 0)))

    def file_percents(self) -> dict[str, float]:
        return {path: percent for path in self.files if (percent := self.file_percent(path)) is not None}

    def directory_percents(self) -> dict[str, float]:
        return {directory: percent for directory in self._directories
                if directory and (percent := self.directory_percent(directory)) is not None}

    @property
    def total(self) -> tuple[int, int]:
        return self._directories.get("", (0, 0))

    def is_stale(self, path: str, modified: float) -> bool:
        return path in self._oldest and modified > self._oldest[path] + STALE_GRACE

    def _add(self, resolver: PathResolver, root: Path, loaded: LoadedReport) -> None:
        place = loaded.path.parent
        directory = place.relative_to(root).as_posix() if place.is_relative_to(root) else ""
        for reported, lines in loaded.report.files.items():
            if not lines:
                continue
            path = resolver.resolve(reported, loaded.report.source_roots, directory)
            if path is None:
                self.unmatched += 1
                continue
            self.files[path] = merge_lines(self.files.get(path, {}), lines)
            self._oldest[path] = min(self._oldest.get(path, loaded.mtime), loaded.mtime)

    def _roll_up(self) -> None:
        for path, lines in self.files.items():
            covered, total = self._file_counts[path] = counts(lines)
            directory = posixpath.dirname(path)
            while True:
                before = self._directories.get(directory, (0, 0))
                self._directories[directory] = (before[0] + covered, before[1] + total)
                if not directory:
                    break
                directory = posixpath.dirname(directory)
