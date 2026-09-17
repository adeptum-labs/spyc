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
from dataclasses import dataclass

from tree_sitter import Parser, QueryCursor

from spyc.languages import Language
from spyc.syntax.grammars import load_tags
from spyc.syntax.tree_sitter_highlighter import compile_query

DEFINITION_PREFIX = "definition."
HEADING = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")


# A definition: line is 1-based and column the 0-based character where the name starts.
@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int
    column: int


def symbols_of(text: str, language: Language | None) -> list[Symbol]:
    if language is None:
        return []
    if language.id == "markdown":
        return _headings(text)
    loaded = load_tags(language)
    return [] if loaded is None else _definitions(text, *loaded)


def _definitions(text: str, ts_language, query_source: str) -> list[Symbol]:
    data = text.encode("utf-8")
    lines = data.split(b"\n")
    tree = Parser(ts_language).parse(data)
    kinds: dict[tuple[str, int, int], str] = {}
    for _, captures in QueryCursor(compile_query(ts_language, query_source)).matches(tree.root_node):
        kind = next((name[len(DEFINITION_PREFIX):] for name in captures if name.startswith(DEFINITION_PREFIX)), None)
        if kind is None or "name" not in captures:
            continue
        node = captures["name"][0]
        row, byte_column = node.start_point
        column = len(lines[row][:byte_column].decode("utf-8", errors="replace"))
        key = (node.text.decode("utf-8", errors="replace"), row + 1, column)
        # Some grammars match a method both as a method and as a function.
        if key not in kinds or (kinds[key] == "function" and kind != "function"):
            kinds[key] = kind
    return sorted((Symbol(name, kind, line, column) for (name, line, column), kind in kinds.items()),
                  key=lambda symbol: (symbol.line, symbol.column))


# Markdown has no grammar here; its headings, outside fenced code, are its outline.
def _headings(text: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    fenced = False
    for number, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and (heading := HEADING.match(line)):
            symbols.append(Symbol(heading["title"], f"h{len(heading['marks'])}", number, heading.start("title")))
    return symbols
