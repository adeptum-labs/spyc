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


# `path` is what the file wrote (dotted for Java, Kotlin and Python, a specifier for scripts), without a
# trailing ".*" (which `wildcard` says). For Python, `level` is the number of leading dots of a relative
# import and `names` what is imported from the module.
@dataclass(frozen=True)
class Import:
    path: str
    wildcard: bool = False
    static: bool = False
    level: int = 0
    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassDef:
    name: str
    line: int


# What one file says about its place in the project: the package (empty for none), the
# top-level types it defines, what it imports, the capitalised names it uses and the
# language it is written in.
@dataclass(frozen=True)
class FileFacts:
    unit: str = ""
    classes: tuple[ClassDef, ...] = ()
    imports: tuple[Import, ...] = ()
    used: frozenset[str] = frozenset()
    language: str = ""


def facts_to_json(facts: FileFacts) -> dict:
    return {"unit": facts.unit, "classes": [[definition.name, definition.line] for definition in facts.classes],
            "imports": [[i.path, i.wildcard, i.static, i.level, list(i.names)] for i in facts.imports],
            "used": sorted(facts.used), "language": facts.language}


# A cache is read back from disk, so what it holds is checked before the graph is built on it.
def facts_from_json(data: dict) -> FileFacts:
    classes = tuple(ClassDef(name, line) for name, line in data["classes"])
    imports = tuple(Import(path, wildcard, static, level, tuple(names))
                    for path, wildcard, static, level, names in data["imports"])
    used, language = frozenset(data["used"]), data["language"]
    if not (isinstance(data["unit"], str) and isinstance(language, str)
            and all(isinstance(c.name, str) and type(c.line) is int for c in classes)
            and all(isinstance(i.path, str) and type(i.wildcard) is bool and type(i.static) is bool
                    and type(i.level) is int and all(isinstance(name, str) for name in i.names) for i in imports)
            and all(isinstance(name, str) for name in used)):
        raise TypeError("facts")
    return FileFacts(data["unit"], classes, imports, used, language)
