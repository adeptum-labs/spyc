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
from collections.abc import Mapping

from spyc.deps.facts import FileFacts, Import

STD_CRATES = frozenset({"std", "core", "alloc"})
RELATIVE = frozenset({"crate", "self", "super"})
MAX_SUPER = 32
MAX_MODULE_DEPTH = 64


# Which module file a Rust path names, worked out from the paths and manifests alone: the root of a crate is
# the lib.rs or main.rs in the src beside its Cargo.toml, which names it, and a module is name.rs or
# name/mod.rs beside its parent.
class RustCrates:
    def __init__(self, files: Mapping[str, FileFacts]) -> None:
        self._paths = {path for path, facts in files.items() if facts.language == "rust"}
        self._root_files = {path for path in self._paths if posixpath.basename(path) in ("lib.rs", "main.rs")}
        self._roots: dict[str, str] = {}
        for path in sorted(self._root_files, reverse=True):
            self._roots[posixpath.dirname(path)] = path
        self._crates: dict[str, str] = {}
        for path, facts in sorted(files.items()):
            root_dir = posixpath.join(posixpath.dirname(path), "src")
            if facts.language == "cargo" and root_dir in self._roots:
                for imported in facts.imports:
                    self._crates.setdefault(imported.path.replace("-", "_"), root_dir)

    # The module file the path reaches and, if it starts with a crate that the project does not hold, its name.
    def resolve(self, importer: str, imported: Import) -> tuple[str | None, str | None]:
        first, *rest = imported.path.split("::")
        if first in STD_CRATES or first[:1].isupper():
            return None, None
        root_dir = self._root_of(importer)
        if first in RELATIVE:
            return self._relative(importer, root_dir, first, rest), None
        if first in self._crates:
            return self._deepest(self._crates[first], rest), None
        if root_dir is not None:
            here = self._module_of(importer, root_dir)
            if self._file_of(root_dir, here + [first]) is not None:
                return self._deepest(root_dir, here + [first] + rest), None
        return None, first

    def _relative(self, importer: str, root_dir: str | None, first: str, rest: list[str]) -> str | None:
        if root_dir is None:
            return None
        here = self._module_of(importer, root_dir)
        if first == "super":
            ups = 1
            while rest[:1] == ["super"] and ups <= MAX_SUPER:
                ups, rest = ups + 1, rest[1:]
            if ups > len(here):
                return None
            here = here[:len(here) - ups]
        elif first == "crate":
            here = []
        return self._deepest(root_dir, here + [name for name in rest if name not in RELATIVE])

    def _root_of(self, path: str) -> str | None:
        directory = posixpath.dirname(path)
        while directory not in self._roots:
            if not directory:
                return None
            directory = posixpath.dirname(directory)
        return directory

    def _module_of(self, path: str, root_dir: str) -> list[str]:
        if path in self._root_files:
            return []
        relative = posixpath.relpath(path, root_dir)[:-3].split("/")
        return relative[:-1] if relative[-1] == "mod" and len(relative) > 1 else relative

    def _file_of(self, root_dir: str, module: list[str]) -> str | None:
        if not module:
            return self._roots.get(root_dir)
        base = posixpath.join(root_dir, *module)
        return next((found for found in (f"{base}.rs", posixpath.join(base, "mod.rs")) if found in self._paths), None)

    # What comes after the last module on the path is an item of it. Modules are not nested thousands deep,
    # and trying every prefix of a path that long would take minutes.
    def _deepest(self, root_dir: str, module: list[str]) -> str | None:
        for length in range(min(len(module), MAX_MODULE_DEPTH), -1, -1):
            if (found := self._file_of(root_dir, module[:length])) is not None:
                return found
        return None
