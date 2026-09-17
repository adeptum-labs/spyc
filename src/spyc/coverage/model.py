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


# A line that runs code. `partial` says that some branch of it was never taken.
@dataclass(frozen=True, slots=True)
class CoverageLine:
    hits: int
    partial: bool = False


Lines = dict[int, CoverageLine]
MAX_DIGITS = 15


@dataclass(frozen=True)
class Report:
    format: str
    files: dict[str, Lines]
    source_roots: tuple[str, ...] = ()


def counts(lines: Lines) -> tuple[int, int]:
    return sum(1 for line in lines.values() if line.hits > 0), len(lines)


# Reports of one run of the tests each cover part of the code, and two reports
# of the same file are one report of it: a line counts as often as the more
# thorough of them ran it, and is partial only if every report that ran it says so.
def merge_line(first: CoverageLine, second: CoverageLine) -> CoverageLine:
    ran = [line.partial for line in (first, second) if line.hits > 0]
    return CoverageLine(max(first.hits, second.hits), bool(ran) and all(ran))


# str.isdigit accepts characters int cannot read, and int refuses more than a few
# thousand digits; a number in a report is ASCII and reasonably short, or not read.
def number_of(text: str) -> int | None:
    return int(text) if text.isascii() and text.isdigit() and len(text) <= MAX_DIGITS else None


# Line numbers count from 1; a report that names line 0 means no line.
def add_line(lines: Lines, number: int, line: CoverageLine) -> None:
    if number >= 1:
        lines[number] = merge_line(lines[number], line) if number in lines else line


def merge_lines(first: Lines, second: Lines) -> Lines:
    merged = dict(first)
    for number, line in second.items():
        add_line(merged, number, line)
    return merged


class ReportError(Exception):
    pass
