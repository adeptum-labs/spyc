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

from tree_sitter import Parser, QueryCursor

from spyc.core.languages import Language
from spyc.syntax.grammars import load_tags
from spyc.syntax.tree_sitter_highlighter import compile_query

DEFINITION_PREFIX = "definition."
CLASS_KINDS = frozenset({"class", "interface", "enum", "type"})
MAX_INDENT = 3
MAX_HEADING_LEVEL = 6
FENCE_CHARACTERS = ("`", "~")
FENCE_LENGTH = 3


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
        return headings_of(text)
    loaded = load_tags(language)
    return [] if loaded is None else _definitions(text, *loaded)


def _definitions(text: str, ts_language, query_source: str) -> list[Symbol]:
    data = text.encode("utf-8")
    return definitions_in(data, Parser(ts_language).parse(data), ts_language, query_source)


def definitions_in(data: bytes, tree, ts_language, query_source: str) -> list[Symbol]:
    lines = data.split(b"\n")
    kinds: dict[tuple[str, int, int], str] = {}
    ascii_rows: dict[int, bool] = {}
    for _, captures in QueryCursor(compile_query(ts_language, query_source)).matches(tree.root_node):
        kind = _kind_of(captures)
        if kind is None or "name" not in captures:
            continue
        node = captures["name"][0]
        row, byte_column = node.start_point
        if row not in ascii_rows:
            ascii_rows[row] = lines[row].isascii()
        column = byte_column if ascii_rows[row] else len(lines[row][:byte_column].decode("utf-8", errors="replace"))
        key = (node.text.decode("utf-8", errors="replace"), row + 1, column)
        # Some grammars match a method both as a method and as a function.
        if key not in kinds or (kinds[key] == "function" and kind != "function"):
            kinds[key] = kind
    return sorted((Symbol(name, kind, line, column) for (name, line, column), kind in kinds.items()),
                  key=lambda symbol: (symbol.line, symbol.column))


def _kind_of(captures) -> str | None:
    return next((name[len(DEFINITION_PREFIX):] for name in captures if name.startswith(DEFINITION_PREFIX)), None)


# The innermost class around a 1-based line, for asking about "this class".
def enclosing_definition(text: str, language: Language | None, line: int) -> Symbol | None:
    loaded = None if language is None or language.id == "markdown" else load_tags(language)
    if loaded is None:
        return None
    ts_language, query_source = loaded
    data = text.encode("utf-8")
    tree = Parser(ts_language).parse(data)
    around = []
    for _, captures in QueryCursor(compile_query(ts_language, query_source)).matches(tree.root_node):
        kind = _kind_of(captures)
        if kind not in CLASS_KINDS or "name" not in captures:
            continue
        whole = next(nodes[0] for name, nodes in captures.items() if name.startswith(DEFINITION_PREFIX))
        if whole.start_point[0] < line <= whole.end_point[0] + 1:
            around.append((whole.end_point[0] - whole.start_point[0], -whole.start_point[0], kind, captures["name"][0]))
    if not around:
        return None
    _, _, kind, name = min(around, key=lambda candidate: candidate[:2])
    row, byte_column = name.start_point
    column = len(data.split(b"\n")[row][:byte_column].decode("utf-8", errors="replace"))
    return Symbol(name.text.decode("utf-8", errors="replace"), kind, row + 1, column)


# Markdown has no grammar here; its headings, outside fenced code, are its outline.
def headings_of(text: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    fence: tuple[str, int] | None = None
    for number, line in enumerate(text.split("\n"), 1):
        marker = _fence_of(line)
        if fence is not None:
            if marker and marker[0] == fence[0] and marker[1] >= fence[1] and line.strip() == marker[0] * marker[1]:
                fence = None
        elif marker:
            fence = marker
        elif heading := _heading_of(line, number):
            symbols.append(heading)
    return symbols


# The character and length of the run that opens or closes a fenced block of code.
def _fence_of(line: str) -> tuple[str, int] | None:
    indent = len(line) - len(line.lstrip(" "))
    if indent > MAX_INDENT or line[indent:indent + 1] not in FENCE_CHARACTERS:
        return None
    run = len(line) - indent - len(line[indent:].lstrip(line[indent]))
    return (line[indent], run) if run >= FENCE_LENGTH else None


# Read by hand: a pattern for this backtracks quadratically over a long run of blanks.
def _heading_of(line: str, number: int) -> Symbol | None:
    indent = len(line) - len(line.lstrip(" "))
    marks = len(line) - indent - len(line[indent:].lstrip("#"))
    rest = line[indent + marks:]
    if indent > MAX_INDENT or not 1 <= marks <= MAX_HEADING_LEVEL or rest[:1] not in ("", " ", "\t"):
        return None
    title = rest.strip(" \t")
    unclosed = title.rstrip("#")
    if unclosed != title and unclosed[-1:] in ("", " ", "\t"):
        title = unclosed.rstrip(" \t")
    if not title:
        return None
    return Symbol(title, f"h{marks}", number, indent + marks + len(rest) - len(rest.lstrip(" \t")))
