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
from collections.abc import Mapping

from spyc.deps.facts import FileFacts, Import

MAX_AMBIGUOUS = 50
MAX_SEGMENTS = 8
EXTERNAL_SEGMENTS = 3


def _shared_directories(directory: str, here: str) -> int:
    shared = 0
    for left, right in zip(directory.split("/"), here.split("/")):
        if left != right:
            break
        shared += 1
    return shared


# Which package of the project a Go import names, and which of its files declare what the importer used.
class GoModules:
    def __init__(self, files: Mapping[str, FileFacts]) -> None:
        self._modules: list[tuple[str, str]] = []
        self._packages: dict[str, list[str]] = defaultdict(list)
        self._defines: dict[str, frozenset[str]] = {}
        for path, facts in sorted(files.items()):
            if facts.language == "gomod":
                self._modules += [(imported.path, posixpath.dirname(path)) for imported in facts.imports]
            elif facts.language == "go" and not path.endswith("_test.go"):
                self._packages[posixpath.dirname(path)].append(path)
                self._defines[path] = facts.defines
        self._modules.sort(key=lambda module: -len(module[0]))
        self._by_tail: dict[str, list[str]] = defaultdict(list)
        for directory in self._packages:
            parts = directory.split("/")
            for start in range(max(len(parts) - MAX_SEGMENTS, 0), len(parts) - 1):
                self._by_tail["/".join(parts[start:])].append(directory)

    # The directory of the package, the files of it that declare a name the importer used, and, for a
    # package that is not the project's, what to call it.
    def resolve(self, importer: str, imported: Import) -> tuple[str | None, set[str], str | None]:
        directory, in_project = self._locate(importer, imported.path)
        if directory is None:
            return None, set(), None if in_project else self._external(imported.path)
        used = set(imported.names)
        return directory, {path for path in self._packages[directory] if self._defines[path] & used}, None

    # The directory, and whether the path is the project's even if no directory has Go files for it.
    def _locate(self, importer: str, path: str) -> tuple[str | None, bool]:
        for module, base in self._modules:
            if path == module or path.startswith(module + "/"):
                directory = posixpath.normpath(posixpath.join(base, path[len(module):].lstrip("/") or "."))
                directory = "" if directory == "." else directory
                return (directory if directory in self._packages else None), True
        if self._modules:
            return None, False
        segments = path.split("/")
        for length in range(len(segments), 1, -1):
            if found := self._by_tail.get("/".join(segments[-length:])):
                return self._nearest(found, posixpath.dirname(importer)), True
        return None, False

    @staticmethod
    def _nearest(directories: list[str], here: str) -> str | None:
        if len(directories) > MAX_AMBIGUOUS:
            return None
        scores = {directory: _shared_directories(directory, here) for directory in directories}
        best = [directory for directory in directories if scores[directory] == max(scores.values())]
        return best[0] if len(best) == 1 else None

    # A path whose first segment has no dot is the standard library, which says nothing about the project.
    @staticmethod
    def _external(path: str) -> str | None:
        segments = path.split("/")
        return "/".join(segments[:EXTERNAL_SEGMENTS]) if "." in segments[0] else None
