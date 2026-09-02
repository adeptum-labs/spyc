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


from collections.abc import Sequence

from rich.cells import cell_len

TAB_SIZE = 4


def _width(char: str, position: int) -> int:
    return TAB_SIZE - position % TAB_SIZE if char == "\t" else cell_len(char)


def cell_of_char(line: str, column: int) -> int:
    if line.isascii() and "\t" not in line:
        return column
    position = 0
    for char in line[:column]:
        position += _width(char, position)
    return position + max(0, column - len(line))


def char_at_cell(line: str, cell: int) -> int:
    position = 0
    for index, char in enumerate(line):
        width = _width(char, position)
        if position + width > cell:
            return index
        position += width
    return len(line)


def line_cells(line: str) -> int:
    return cell_of_char(line, len(line))


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
