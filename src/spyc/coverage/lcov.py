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


from spyc.coverage.model import CoverageLine, Lines, Report, add_line


# Records start at SF: and end at end_of_record. DA:line,hits[,checksum] says how
# often a line ran; BRDA:line,block,branch,taken has "-" or 0 for a branch never taken.
def parse_lcov(text: str) -> Report:
    files: dict[str, Lines] = {}
    lines: Lines | None = None
    partial: set[int] = set()
    for row in text.splitlines():
        tag, _, value = row.partition(":")
        if tag == "SF":
            lines = files.setdefault(value, {})
        elif tag == "DA" and lines is not None:
            _add_line(lines, value)
        elif tag == "BRDA" and lines is not None:
            _note_branch(partial, value)
        elif tag == "end_of_record" and lines is not None:
            _close_record(lines, partial)
            lines = None
    return Report("LCOV", files)


def _add_line(lines: Lines, value: str) -> None:
    fields = value.split(",")
    if len(fields) < 2 or not fields[0].isdigit() or not fields[1].isdigit():
        return
    add_line(lines, int(fields[0]), CoverageLine(int(fields[1])))


def _note_branch(partial: set[int], value: str) -> None:
    fields = value.split(",")
    if len(fields) == 4 and fields[0].isdigit() and fields[3] in ("-", "0"):
        partial.add(int(fields[0]))


def _close_record(lines: Lines, partial: set[int]) -> None:
    for number in partial & lines.keys():
        if lines[number].hits > 0:
            lines[number] = CoverageLine(lines[number].hits, partial=True)
    partial.clear()
