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


from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    is_dir: bool


class TreeModel:
    def __init__(self, paths: Iterable[str]) -> None:
        self._children: dict[str, dict[str, Entry]] = {"": {}}
        for path in paths:
            parent = ""
            parts = path.split("/")
            for index, name in enumerate(parts):
                child = f"{parent}/{name}" if parent else name
                siblings = self._children[parent]
                if name not in siblings:
                    is_dir = index < len(parts) - 1
                    siblings[name] = Entry(name, child, is_dir)
                    if is_dir:
                        self._children[child] = {}
                parent = child

    def children(self, directory: str) -> list[Entry]:
        entries = sorted(self._children.get(directory, {}).values(),
                         key=lambda entry: (not entry.is_dir, entry.name.lower(), entry.name))
        return [self._compacted(entry) for entry in entries]

    # Java-style trees are mostly chains such as src/main/java/com/acme, which
    # would otherwise cost one keypress per level.
    def _compacted(self, entry: Entry) -> Entry:
        while entry.is_dir and len(self._children[entry.path]) == 1:
            (only,) = self._children[entry.path].values()
            if not only.is_dir:
                break
            entry = Entry(f"{entry.name}/{only.name}", only.path, True)
        return entry

    def directories_above(self, path: str) -> list[Entry]:
        chain: list[Entry] = []
        directory = ""
        while True:
            entry = next((entry for entry in self.children(directory)
                          if entry.is_dir and path.startswith(f"{entry.path}/")), None)
            if entry is None:
                return chain
            chain.append(entry)
            directory = entry.path
