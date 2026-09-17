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


# `path` is dotted, as written, without a trailing ".*" (which `wildcard` says).
@dataclass(frozen=True)
class Import:
    path: str
    wildcard: bool = False
    static: bool = False


@dataclass(frozen=True)
class ClassDef:
    name: str
    line: int


# What one file says about its place in the project: the package (empty for none), the
# top-level types it defines, what it imports and the capitalised names it uses.
@dataclass(frozen=True)
class FileFacts:
    unit: str = ""
    classes: tuple[ClassDef, ...] = ()
    imports: tuple[Import, ...] = ()
    used: frozenset[str] = frozenset()


def facts_to_json(facts: FileFacts) -> dict:
    return {"unit": facts.unit, "classes": [[definition.name, definition.line] for definition in facts.classes],
            "imports": [[imported.path, imported.wildcard, imported.static] for imported in facts.imports],
            "used": sorted(facts.used)}


def facts_from_json(data: dict) -> FileFacts:
    if not isinstance(data["unit"], str):
        raise TypeError("unit")
    return FileFacts(data["unit"], tuple(ClassDef(name, line) for name, line in data["classes"]),
                     tuple(Import(path, wildcard, static) for path, wildcard, static in data["imports"]),
                     frozenset(data["used"]))
