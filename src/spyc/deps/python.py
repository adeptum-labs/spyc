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
import sys
from collections import defaultdict
from collections.abc import Iterable

from spyc.deps.facts import Import

STDLIB = sys.stdlib_module_names
MAX_AMBIGUOUS = 50


def _shared_directories(path: str, directory: str) -> int:
    shared = 0
    for left, right in zip(path.split("/")[:-1], directory.split("/")):
        if left != right:
            break
        shared += 1
    return shared


# Which project file a Python import names, worked out from the paths alone.
class PythonModules:
    def __init__(self, paths: Iterable[str]) -> None:
        self._paths = {path for path in paths if path.endswith(".py")}
        self._by_module: dict[str, list[str]] = defaultdict(list)
        for path in sorted(self._paths):
            parts = path[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            for start in range(len(parts)):
                self._by_module[".".join(parts[start:])].append(path)

    # The project files the import reaches and, if none, the name of what it is outside the project.
    def resolve(self, importer: str, imported: Import) -> tuple[set[str], str | None]:
        if imported.level:
            return self._relative(importer, imported), None
        module = (self._nearest(imported.path, importer) if imported.names or imported.wildcard
                  else self._longest(imported.path, importer))
        targets = {found for name in imported.names if (found := self._nearest(f"{imported.path}.{name}", importer))}
        if imported.wildcard or (imported.names and not targets) or not imported.names:
            targets |= {module} if module else set()
        if targets:
            return targets, None
        first = imported.path.split(".")[0]
        return set(), None if first in STDLIB or first in self._by_module else first

    def _longest(self, dotted: str, importer: str) -> str | None:
        segments = dotted.split(".")
        for length in range(len(segments), 0, -1):
            if (found := self._nearest(".".join(segments[:length]), importer)) is not None:
                return found
        return None

    # The module in the directory of the importer or of one above it, the nearest first, as when a script
    # is run from where it lies; else the only module of that name, or the nearest one if it is not too common.
    def _nearest(self, dotted: str, importer: str) -> str | None:
        relative, directory = dotted.replace(".", "/"), posixpath.dirname(importer)
        while True:
            base = posixpath.join(directory, relative)
            if (found := next((c for c in (f"{base}.py", f"{base}/__init__.py") if c in self._paths), None)) is not None:
                return found
            if not directory:
                break
            directory = posixpath.dirname(directory)
        candidates = self._by_module.get(dotted, [])
        if not candidates or len(candidates) > MAX_AMBIGUOUS:
            return None
        here = posixpath.dirname(importer)
        scores = {path: _shared_directories(path, here) for path in candidates}
        best = [path for path in candidates if scores[path] == max(scores.values())]
        return best[0] if len(best) == 1 else None

    def _relative(self, importer: str, imported: Import) -> set[str]:
        directory = posixpath.dirname(importer)
        for _ in range(imported.level - 1):
            if not directory:
                return set()
            directory = posixpath.dirname(directory)
        base = posixpath.join(directory, *imported.path.split(".")) if imported.path else directory
        module = next((found for found in (f"{base}.py", f"{base}/__init__.py") if found in self._paths), None)
        targets = {found for name in imported.names
                   if (found := next((c for c in (f"{base}/{name}.py", f"{base}/{name}/__init__.py") if c in self._paths), None))}
        if imported.wildcard or (imported.names and not targets) or not imported.names:
            targets |= {module} if module else set()
        return targets
