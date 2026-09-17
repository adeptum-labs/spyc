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


from spyc.coverage.model import CoverageLine, Lines, Report, add_line, merge_lines, number_of


# Records start at SF: and end at end_of_record, or at the next SF:. DA:line,hits[,checksum]
# says how often a line ran; BRDA:line,block,branch,taken has "-" or 0 for a branch never
# taken. Each record is read on its own and then merged into its file, so what one record
# says about branches never spills into another record or another file.
def parse_lcov(text: str) -> Report:
    files: dict[str, Lines] = {}
    name: str | None = None
    record: Lines = {}
    partial: set[int] = set()
    for row in [*text.removeprefix("\ufeff").splitlines(), "end_of_record"]:
        tag, _, value = row.partition(":")
        if tag in ("SF", "end_of_record"):
            if name is not None and record:
                files[name] = merge_lines(files.get(name, {}), _with_partial_lines(record, partial))
            name, record, partial = (value if tag == "SF" else None), {}, set()
        elif name is not None and tag == "DA":
            _add_line(record, value)
        elif name is not None and tag == "BRDA":
            _note_branch(partial, value)
    return Report("LCOV", files)


def _add_line(lines: Lines, value: str) -> None:
    fields = value.split(",")
    number, hits = (number_of(field) for field in fields[:2]) if len(fields) >= 2 else (None, None)
    if number is not None and hits is not None:
        add_line(lines, number, CoverageLine(hits))


def _note_branch(partial: set[int], value: str) -> None:
    fields = value.split(",")
    number = number_of(fields[0]) if len(fields) == 4 and fields[3] in ("-", "0") else None
    if number is not None:
        partial.add(number)


def _with_partial_lines(record: Lines, partial: set[int]) -> Lines:
    return {number: CoverageLine(line.hits, partial=number in partial and line.hits > 0)
            for number, line in record.items()}
