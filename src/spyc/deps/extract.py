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
from collections.abc import Iterator
from itertools import islice

from tree_sitter import QueryCursor

from spyc.deps.facts import ClassDef, FileFacts, Import

MAX_IMPORTS = 5000
MAX_USED = 2000
MAX_CLASSES = 100
MAX_USE_DEPTH = 16
MAX_PARENT_WALK = 256
PATH_NODES = frozenset({"identifier", "crate", "self", "super", "scoped_identifier"})
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


def _joined(prefix: str, text: str) -> str:
    return f"{prefix}::{text}" if prefix and text else prefix or text


# Every path a Rust use declaration names: use a::{b, c::d, self} is a::b, a::c::d and a. The tree is walked
# with a stack of its own and not deeper than MAX_USE_DEPTH, since a hostile file can nest it thousands deep.
def _use_paths(root) -> Iterator[tuple[str, bool]]:
    stack = [(root, "", 0)]
    while stack:
        node, prefix, depth = stack.pop()
        if node is None or depth > MAX_USE_DEPTH:
            continue
        if node.type in PATH_NODES:
            text = _text(node)
            yield (prefix if text == "self" and prefix else _joined(prefix, text)), False
        elif node.type == "use_as_clause":
            stack.append((node.child_by_field_name("path"), prefix, depth))
        elif node.type == "use_wildcard":
            inner = node.named_children[0] if node.named_children else None
            yield _joined(prefix, _text(inner) if inner is not None else ""), True
        elif node.type == "scoped_use_list":
            path = node.child_by_field_name("path")
            stack.append((node.child_by_field_name("list"), _joined(prefix, _text(path)) if path is not None else prefix, depth + 1))
        elif node.type == "use_list":
            stack.extend((child, prefix, depth + 1) for child in reversed(node.named_children))


# The inline modules a declaration is inside, outermost first; None for one nested too deep to be read.
def _inline_modules(node) -> list[str] | None:
    names, parent = [], node.parent
    for _ in range(MAX_PARENT_WALK):
        if parent is None:
            return names[::-1]
        if parent.type == "mod_item":
            name = parent.child_by_field_name("name")
            names.append(_text(name) if name is not None else "")
            if len(names) > MAX_USE_DEPTH:
                return None
        parent = parent.parent
    return None


# A path written inside inline modules, as one from the module of the file: in mod tests { use super::*; }
# the super is the file's own module, which is no dependency, and not the module above the file.
def _within(path: str, modules: list[str]) -> str:
    segments = path.split("::")
    if not modules or segments[0] not in ("self", "super"):
        return path
    rest, here = (segments[1:] if segments[0] == "self" else segments), modules
    while rest[:1] == ["super"] and here:
        rest, here = rest[1:], here[:-1]
    return "::".join(rest if rest[:1] == ["super"] else ["self", *here, *rest])


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
        elif "use" in captures:
            modules = _inline_modules(captures["use"][0])
            paths = _use_paths(captures["use"][0].child_by_field_name("argument")) if modules is not None else ()
            imports += (Import(_within(path, modules), wildcard) for path, wildcard in islice(paths, MAX_IMPORTS - len(imports)))
        elif "mod" in captures:
            modules = _inline_modules(captures["mod"][0].parent)
            if len(imports) < MAX_IMPORTS and modules is not None:
                imports.append(Import(_within(f"self::{_text(captures['mod'][0])}", modules)))
        elif "include" in captures:
            if len(imports) < MAX_IMPORTS:
                imports.append(Import(_text(captures["include"][0])))
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
