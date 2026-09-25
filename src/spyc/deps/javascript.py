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
from collections.abc import Iterable

# TypeScript is imported as if it were the JavaScript it becomes: './x.js' can be x.ts.
TS_FOR = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}
EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".json")


def package_name(specifier: str) -> str:
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") and len(parts) > 1 else parts[0]


# Which project file an import or require of a script names, worked out from the paths alone.
# Only relative specifiers are files of the project; path aliases of a tsconfig are not followed.
class ScriptModules:
    def __init__(self, paths: Iterable[str]) -> None:
        self._paths = set(paths)

    def resolve(self, importer: str, specifier: str) -> tuple[str | None, str | None]:
        if not specifier.startswith("."):
            return None, None if specifier.startswith("/") else package_name(specifier)
        target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), specifier))
        if target.startswith(".."):
            return None, None
        target = "" if target == "." else target
        stem, extension = posixpath.splitext(target)
        candidates = [target, *(stem + other for other in TS_FOR.get(extension, ())),
                      *(target + suffix for suffix in EXTENSIONS),
                      *(posixpath.join(target, f"index{suffix}") for suffix in EXTENSIONS)]
        return next((found for found in candidates if found in self._paths), None), None
