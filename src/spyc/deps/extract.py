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


import re

from tree_sitter import QueryCursor

from spyc.deps.facts import ClassDef, FileFacts, Import

MAX_IMPORTS = 5000
MAX_USED = 2000
MAX_CLASSES = 100
VERSION = re.compile(r"^v[0-9]+$")
VERSION_SUFFIX = re.compile(r"\.v[0-9]+$")


def _text(node) -> str:
    return "".join(node.text.decode("utf-8", errors="replace").split())


# The name a Go package is called by when its import gives none: the last segment, but not a version.
def _default_alias(path: str) -> str:
    segments = path.split("/")
    name = segments[-2] if len(segments) > 1 and VERSION.match(segments[-1]) else segments[-1]
    return VERSION_SUFFIX.sub("", name)


# import str "strings"  /  import . "x"  /  import _ "x"  /  import "x/y/v2"
def _go_import(spec, selectors: dict[str, set[str]]) -> Import:
    path = _text(spec.child_by_field_name("path")).strip("\"`")
    name = spec.child_by_field_name("name")
    dotted = name is not None and name.type == "dot"
    alias = None if name is not None and name.type in ("dot", "blank_identifier") else (
        _text(name) if name is not None else _default_alias(path))
    return Import(path, dotted, False, 0, tuple(sorted(selectors.get(alias, ()))))


# from a.b import c as d, e   /   from ..pkg import x   /   from . import y   /   from a import *
def _from_import(statement) -> Import:
    module, level, path = statement.child_by_field_name("module_name"), 0, ""
    if module is not None and module.type == "relative_import":
        prefix = next((child for child in module.children if child.type == "import_prefix"), None)
        level = len(prefix.text) if prefix is not None else 1
        dotted = next((child for child in module.children if child.type == "dotted_name"), None)
        path = _text(dotted) if dotted is not None else ""
    elif module is not None:
        path = _text(module)
    names = tuple(_text(child.child_by_field_name("name") or child) for child in statement.children_by_field_name("name"))
    wildcard = any(child.type == "wildcard_import" for child in statement.children)
    return Import(path, wildcard, False, level, names)


# The package of a file, the classes it defines, what it imports and the capitalised
# names it uses (identifier nodes only, so comments and strings do not count).
def facts_of(tree, query) -> FileFacts:
    unit, classes, imports, used = "", [], [], set()
    specs, selectors, selected, defines = [], {}, 0, set()
    for _, captures in QueryCursor(query).matches(tree.root_node):
        if "package" in captures:
            unit = _text(captures["package"][0])
        elif "class" in captures:
            node = captures["class"][0]
            if len(classes) < MAX_CLASSES:
                classes.append(ClassDef(_text(node), node.start_point[0] + 1))
        elif "from" in captures:
            if len(imports) < MAX_IMPORTS:
                imports.append(_from_import(captures["from"][0]))
        elif "path" in captures:
            if len(imports) < MAX_IMPORTS:
                imports.append(Import(_text(captures["path"][0]), "wildcard" in captures, "static" in captures))
        elif "spec" in captures:
            if len(specs) < MAX_IMPORTS:
                specs.append(captures["spec"][0])
        elif "operand" in captures:
            if selected < MAX_USED:
                field, names = _text(captures["field"][0]), selectors.setdefault(_text(captures["operand"][0]), set())
                selected += field not in names
                names.add(field)
        elif "define" in captures:
            if len(defines) < MAX_USED:
                defines.add(_text(captures["define"][0]))
        elif len(used) < MAX_USED:
            name = captures["name"][0].text.decode("utf-8", errors="replace")
            if name[:1].isupper():
                used.add(name)
    imports += (_go_import(spec, selectors) for spec in specs)
    return FileFacts(unit, tuple(classes), tuple(imports), frozenset(used), defines=frozenset(defines))
