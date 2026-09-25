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
MAX_SEGMENTS = 8
MAX_WALK = 32


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
        self._packages = {posixpath.dirname(path) for path in self._paths if posixpath.basename(path) == "__init__.py"}
        self._by_module: dict[str, list[str]] = defaultdict(list)
        self._walked: dict[tuple[str, str], str | None] = {}
        for path in sorted(self._paths):
            parts = path[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            for start in self._importable_starts(parts):
                self._by_module[".".join(parts[start:])].append(path)

    # A module can be imported by the end of its path only where that end starts in a directory that is not a
    # package (a source root, or a directory of scripts); the whole path always names it from the project root.
    # Only the last few segments are indexed, since a deeper dotted name is not written.
    def _importable_starts(self, parts: list[str]) -> list[int]:
        if not parts:
            return []
        candidates = {0, *range(max(len(parts) - MAX_SEGMENTS, 0), len(parts))}
        return [start for start in sorted(candidates) if start == 0 or "/".join(parts[:start]) not in self._packages]

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

    # A module of the project that an absolute import can name: one beside the script that imports it, or above
    # it, in a directory that is not a package; else one that can be imported from a source root, the only one of
    # its name or the nearest if it is not too common. The standard library is not looked for in the project
    # beyond the directories of scripts, and a file is never what it imports itself.
    def _nearest(self, dotted: str, importer: str) -> str | None:
        here = posixpath.dirname(importer)
        found = self._walk(dotted, here)
        if found == importer:
            found = self._walk(dotted, posixpath.dirname(here)) if here else None
        if found is not None or dotted.split(".")[0] in STDLIB:
            return found
        return self._anywhere(dotted, importer, here)

    def _walk(self, dotted: str, directory: str) -> str | None:
        key = (dotted, directory)
        if key not in self._walked:
            self._walked[key] = self._look_upwards(dotted, directory)
        return self._walked[key]

    def _look_upwards(self, dotted: str, directory: str) -> str | None:
        relative = dotted.replace(".", "/")
        for _ in range(MAX_WALK):
            if directory not in self._packages:
                base = posixpath.join(directory, relative)
                if (found := next((c for c in (f"{base}.py", f"{base}/__init__.py") if c in self._paths), None)) is not None:
                    return found
            if directory in ("", "/"):
                break
            directory = posixpath.dirname(directory)
        return None

    def _anywhere(self, dotted: str, importer: str, here: str) -> str | None:
        candidates = [path for path in self._by_module.get(dotted, []) if path != importer]
        if not candidates or len(candidates) > MAX_AMBIGUOUS:
            return None
        scores = {path: _shared_directories(path, here) for path in candidates}
        highest = max(scores.values())
        best = [path for path in candidates if scores[path] == highest]
        return best[0] if len(best) == 1 else None

    def _relative(self, importer: str, imported: Import) -> set[str]:
        directory = posixpath.dirname(importer)
        for _ in range(imported.level - 1):
            if not directory:
                return set()
            directory = posixpath.dirname(directory)
        base = posixpath.join(directory, *imported.path.split(".")) if imported.path else directory
        module = next((found for found in ([f"{base}.py"] if base else []) + [posixpath.join(base, "__init__.py")]
                       if found in self._paths), None)
        targets = {found for name in imported.names
                   if (found := next((c for c in (posixpath.join(base, f"{name}.py"), posixpath.join(base, name, "__init__.py"))
                                      if c in self._paths), None))}
        if imported.wildcard or (imported.names and not targets) or not imported.names:
            targets |= {module} if module else set()
        return targets
