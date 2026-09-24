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


from tree_sitter import QueryCursor

from spyc.deps.facts import ClassDef, FileFacts, Import

MAX_IMPORTS = 5000
MAX_USED = 2000
MAX_CLASSES = 100


def _text(node) -> str:
    return "".join(node.text.decode("utf-8", errors="replace").split())


# The package of a file, the classes it defines, what it imports and the capitalised
# names it uses (identifier nodes only, so comments and strings do not count).
def facts_of(tree, query) -> FileFacts:
    unit, classes, imports, used = "", [], [], set()
    for _, captures in QueryCursor(query).matches(tree.root_node):
        if "package" in captures:
            unit = _text(captures["package"][0])
        elif "class" in captures:
            node = captures["class"][0]
            if len(classes) < MAX_CLASSES:
                classes.append(ClassDef(_text(node), node.start_point[0] + 1))
        elif "path" in captures:
            if len(imports) < MAX_IMPORTS:
                imports.append(Import(_text(captures["path"][0]), "wildcard" in captures, "static" in captures))
        elif len(used) < MAX_USED:
            name = captures["name"][0].text.decode("utf-8", errors="replace")
            if name[:1].isupper():
                used.add(name)
    return FileFacts(unit, tuple(classes), tuple(imports), frozenset(used))
