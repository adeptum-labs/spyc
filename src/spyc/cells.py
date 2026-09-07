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


from bisect import bisect_right
from collections.abc import Iterable, Sequence
from functools import lru_cache

from rich.cells import cell_len

TAB_SIZE = 4
CHECKPOINT = 2048


def _width(char: str, position: int) -> int:
    return TAB_SIZE - position % TAB_SIZE if char == "\t" else cell_len(char)


def _is_simple(line: str) -> bool:
    return line.isascii() and "\t" not in line


# Walking a minified bundle of megabytes character by character on every
# cursor move would take seconds, so long lines are measured once at every
# CHECKPOINT characters and a position is found from the nearest checkpoint.
@lru_cache(maxsize=4)
def _checkpoints(line: str) -> tuple[list[int], list[int]]:
    chars, cells, position = [0], [0], 0
    for index, char in enumerate(line, 1):
        position += _width(char, position)
        if index % CHECKPOINT == 0:
            chars.append(index)
            cells.append(position)
    return chars, cells


def cell_of_char(line: str, column: int) -> int:
    if _is_simple(line):
        return column
    start, position = 0, 0
    if len(line) > CHECKPOINT:
        chars, cells = _checkpoints(line)
        nearest = min(bisect_right(chars, column) - 1, len(chars) - 1)
        start, position = chars[nearest], cells[nearest]
    for char in line[start:column]:
        position += _width(char, position)
    return position + max(0, column - len(line))


def char_at_cell(line: str, cell: int) -> int:
    start, position = 0, 0
    if len(line) > CHECKPOINT:
        chars, cells = _checkpoints(line)
        nearest = max(bisect_right(cells, cell) - 1, 0)
        start, position = chars[nearest], cells[nearest]
    for index in range(start, len(line)):
        width = _width(line[index], position)
        if position + width > cell:
            return index
        position += width
    return len(line)


def line_cells(line: str) -> int:
    return cell_of_char(line, len(line))


def widest_cells(lines: Iterable[str]) -> int:
    lines = list(lines)
    widest = max(map(len, lines), default=0)
    return max([widest, *(line_cells(line) for line in lines if not _is_simple(line))])


def expand_tabs(line: str) -> tuple[str, Sequence[int]]:
    if "\t" not in line:
        return line, range(len(line) + 1)
    pieces: list[str] = []
    starts: list[int] = []
    position = length = 0
    for char in line:
        starts.append(length)
        width = _width(char, position)
        pieces.append(" " * width if char == "\t" else char)
        position += width
        length += width if char == "\t" else 1
    starts.append(length)
    return "".join(pieces), starts
