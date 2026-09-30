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
from collections.abc import Iterable

MAX_AMBIGUOUS = 50
MAX_WALK = 32
LIBRARY_DIRECTORIES = ("include", "inc")
INCLUDE_DIRECTORIES = ("", *LIBRARY_DIRECTORIES, "src")
# The header directories of the system say nothing about the project, as its other system headers do not.
OPERATING_SYSTEM_DIRECTORIES = frozenset({"sys", "arpa", "netinet", "net", "linux", "asm", "bits"})


def _shared_directories(path: str, here: str) -> int:
    shared = 0
    for left, right in zip(path.split("/")[:-1], here.split("/")):
        if left != right:
            break
        shared += 1
    return shared


# Which header or source of the project an include names, worked out from the paths alone: beside the
# including file (quoted includes only), in an include directory of it or of a directory above, else by the
# end of its path. An angle include is looked for where a compiler is told to look and not beside the
# file, and one without a directory (<stdint.h>) is a system header unless the project keeps it in an
# include directory: a project often has its own copy of a system header for one platform.
class IncludeModules:
    def __init__(self, paths: Iterable[str]) -> None:
        self._paths = set(paths)
        self._by_name: dict[str, list[str]] = defaultdict(list)
        for path in sorted(self._paths):
            self._by_name[posixpath.basename(path)].append(path)
        self._ends: dict[tuple[str, bool], list[str]] = {}
        self._searched: dict[tuple[str, str, bool], str | None] = {}

    # The path reached and, for a library header that is not in the project, the name of the library.
    def resolve(self, importer: str, include: str) -> tuple[str | None, str | None]:
        quoted, spec = include.startswith('"'), include[1:-1]
        here = posixpath.dirname(importer)
        if quoted and (beside := posixpath.normpath(posixpath.join(here, spec))) in self._paths:
            return beside, None
        found = self._search(spec, here, quoted) or self._by_end(spec, here, quoted)
        if found is not None or quoted or "/" not in spec:
            return found, None
        library = spec.split("/")[0]
        return None, None if library in OPERATING_SYSTEM_DIRECTORIES else library

    def _search(self, spec: str, here: str, quoted: bool) -> str | None:
        key = (spec, here, quoted)
        if key not in self._searched:
            self._searched[key] = self._look_upwards(spec, here, quoted)
        return self._searched[key]

    def _look_upwards(self, spec: str, directory: str, quoted: bool) -> str | None:
        for level in range(MAX_WALK):
            for prefix in INCLUDE_DIRECTORIES:
                if (prefix or quoted or level) and (
                        candidate := posixpath.normpath(posixpath.join(directory, prefix, spec))) in self._paths:
                    return candidate
            if not directory:
                break
            directory = posixpath.dirname(directory)
        return None

    def _by_end(self, spec: str, here: str, quoted: bool) -> str | None:
        system_name = not quoted and "/" not in spec
        if (spec, system_name) not in self._ends:
            named = self._by_name.get(posixpath.basename(spec), [])
            if system_name:
                named = [path for path in named if posixpath.basename(posixpath.dirname(path)) in LIBRARY_DIRECTORIES]
            elif "/" in spec and len(named) <= MAX_AMBIGUOUS:
                named = [path for path in named if path == spec or path.endswith("/" + spec)]
            self._ends[spec, system_name] = named
        candidates = self._ends[spec, system_name]
        if not candidates or len(candidates) > MAX_AMBIGUOUS:
            return None
        scores = {path: _shared_directories(path, here) for path in candidates}
        best = [path for path in candidates if scores[path] == max(scores.values())]
        return best[0] if len(best) == 1 else None
