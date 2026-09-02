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


from functools import cache

from tree_sitter import Language, Parser, Query, QueryCursor

from spyc.syntax.spans import Span

BLOCK_LINES = 64


@cache
def compile_query(language: Language, source: str) -> Query:
    return Query(language, source)


# Nodes are painted outer first, so an inner node overwrites the node around it.
# Among patterns capturing the same node the lowest pattern index wins.
class TreeSitterHighlighter:
    def __init__(self, text: str, language: Language, query_source: str) -> None:
        self._blocks: dict[int, list[list[Span]]] = {}
        self._lines = text.split("\n")
        self._encoded = [line.encode("utf-8") for line in self._lines]
        self._query = compile_query(language, query_source)
        self._tree = Parser(language).parse("\n".join(self._lines).encode("utf-8"))

    # Scrolling asks for a few lines at a time; querying whole blocks and
    # keeping them makes every later call for the same lines a lookup.
    def spans(self, first: int, stop: int) -> list[list[Span]]:
        if stop <= first:
            return []
        blocks = range(first // BLOCK_LINES, (stop - 1) // BLOCK_LINES + 1)
        lines = [line for block in blocks for line in self._block(block)]
        offset = first - blocks.start * BLOCK_LINES
        return lines[offset:offset + stop - first]

    def _block(self, index: int) -> list[list[Span]]:
        if index not in self._blocks:
            self._blocks[index] = self._paint(index * BLOCK_LINES, (index + 1) * BLOCK_LINES)
        return self._blocks[index]

    def _paint(self, first: int, stop: int) -> list[list[Span]]:
        last = min(stop, len(self._lines))
        if first >= last:
            return [[] for _ in range(first, stop)]
        painted = {row: [None] * len(self._lines[row]) for row in range(first, last)}
        for (start, end), capture in self._captured_nodes(first, last):
            for row in range(max(start[0], first), min(end[0], last - 1) + 1):
                width = len(self._lines[row])
                begin = self._column(row, start[1]) if row == start[0] else 0
                finish = min(self._column(row, end[1]) if row == end[0] else width, width)
                if finish > begin:
                    painted[row][begin:finish] = [capture] * (finish - begin)
        return [_runs(painted[row]) if row in painted else [] for row in range(first, stop)]

    def _captured_nodes(self, first: int, last: int) -> list[tuple[tuple, str]]:
        cursor = QueryCursor(self._query)
        cursor.set_point_range((first, 0), (last, 0))
        chosen: dict[tuple, tuple[int, str]] = {}
        for pattern, captures in cursor.matches(self._tree.root_node):
            for capture, nodes in captures.items():
                if capture.startswith("_"):
                    continue
                for node in nodes:
                    key = (tuple(node.start_point), tuple(node.end_point))
                    if key not in chosen or pattern < chosen[key][0]:
                        chosen[key] = (pattern, capture)
        outer_first = sorted(chosen, key=lambda key: (key[0], (-key[1][0], -key[1][1])))
        return [(key, chosen[key][1]) for key in outer_first]

    def _column(self, row: int, byte_column: int) -> int:
        encoded = self._encoded[row]
        if len(encoded) == len(self._lines[row]):
            return byte_column
        return len(encoded[:byte_column].decode("utf-8", errors="replace"))


def _runs(painted: list[str | None]) -> list[Span]:
    runs: list[Span] = []
    start = 0
    for column in range(1, len(painted) + 1):
        if column == len(painted) or painted[column] != painted[start]:
            if painted[start] is not None:
                runs.append(Span(start, column, painted[start]))
            start = column
    return runs
