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
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path


def _normalized(path: str) -> str:
    path = path.strip().replace("\\", "/")
    return posixpath.normpath(path) if path else ""


def _shared_directories(path: str, directory: str) -> int:
    shared = 0
    for left, right in zip(path.split("/")[:-1], directory.split("/")):
        if left != right:
            break
        shared += 1
    return shared


# A report names its files as the build that made it saw them: relative to the
# project, absolute in a checkout elsewhere, as a package path (Java) or an import
# path (Go). What the project has is matched to that: exactly, then through the
# source roots of the report, then by the ends of the paths, where the longest
# end wins and a tie is broken by the place of the report, or else left unmatched.
class PathResolver:
    def __init__(self, root: Path, paths: Iterable[str]) -> None:
        self._prefix = root.as_posix().rstrip("/") + "/"
        self._known = frozenset(paths)
        self._by_name: dict[str, list[str]] = defaultdict(list)
        for path in self._known:
            self._by_name[posixpath.basename(path)].append(path)

    def resolve(self, reported: str, source_roots: Sequence[str] = (), report_directory: str = "") -> str | None:
        name = _normalized(reported)
        if not name:
            return None
        for candidate in (name, *(f"{_normalized(source_root)}/{name}" for source_root in source_roots)):
            if (found := self._inside_project(candidate)) is not None:
                return found
        return self._by_suffix(name, _normalized(report_directory) if report_directory else "")

    def _inside_project(self, candidate: str) -> str | None:
        relative = candidate.removeprefix(self._prefix)
        return relative if relative in self._known else None

    def _by_suffix(self, name: str, report_directory: str) -> str | None:
        length = len(name.split("/"))
        fitting = {path: min(length, len(path.split("/"))) for path in self._by_name.get(name.rpartition("/")[2], [])
                   if name == path or name.endswith(f"/{path}") or path.endswith(f"/{name}")}
        best = [path for path in fitting if fitting[path] == max(fitting.values())]
        if len(best) > 1:
            nearest = max(_shared_directories(path, report_directory) for path in best)
            best = [path for path in best if _shared_directories(path, report_directory) == nearest]
        return best[0] if len(best) == 1 else None
