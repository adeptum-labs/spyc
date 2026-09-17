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
from collections import defaultdict

from spyc.coverage.model import CoverageLine, Lines, Report

BLOCK = re.compile(r"^(?P<file>.+):(?P<start>[0-9]{1,12})\.(?P<from>[0-9]{1,12}),(?P<end>[0-9]{1,12})\.(?P<to>[0-9]{1,12}) "
                   r"[0-9]{1,12} (?P<count>[0-9]{1,15})$")
# A function is not thousands of lines long; a block that says it is, is not expanded, and a
# report is only expanded so far, because every line costs memory whatever the file is.
MAX_BLOCK_LINES = 50_000
MAX_EXPANDED_LINES = 3_000_000


# A block of statements runs from a line to a line, and a line is the more
# covered the more of the blocks over it ran: partial if only some did. The same
# block in the profiles of several packages counts as often as its best profile.
def parse_gocover(text: str) -> Report:
    counts: dict[tuple, int] = {}
    for row in text.removeprefix("\ufeff").splitlines():
        block = BLOCK.match(row)
        if block is not None and 1 <= int(block["start"]) <= int(block["end"]) and \
                int(block["end"]) - int(block["start"]) < MAX_BLOCK_LINES:
            key = block.group("file", "start", "from", "end", "to")
            counts[key] = max(counts.get(key, 0), int(block["count"]))
    return Report("Go", {name: _lines_of(states) for name, states in _expand(counts).items()})


# The best count of a line, shifted left, with a low bit that says a block over it did not run.
def _expand(counts: dict[tuple, int]) -> dict[str, dict[int, int]]:
    states: dict[str, dict[int, int]] = defaultdict(dict)
    budget = MAX_EXPANDED_LINES
    for (name, start, _, end, _), count in counts.items():
        budget -= int(end) - int(start) + 1
        if budget < 0:
            break
        lines, missed = states[name], int(count == 0)
        for number in range(int(start), int(end) + 1):
            state = lines.get(number, 0)
            lines[number] = max(state >> 1, count) << 1 | ((state | missed) & 1)
    return states


def _lines_of(states: dict[int, int]) -> Lines:
    return {number: CoverageLine(state >> 1, partial=state >> 1 > 0 and bool(state & 1)) for number, state in states.items()}
