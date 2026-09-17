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

BLOCK = re.compile(r"^(?P<file>.+):(?P<start>\d+)\.(?P<from>\d+),(?P<end>\d+)\.(?P<to>\d+) \d+ (?P<count>\d+)$")


# A block of statements runs from a line to a line, and a line is the more
# covered the more of the blocks over it ran: partial if only some did. The same
# block in the profiles of several packages counts as often as its best profile.
def parse_gocover(text: str) -> Report:
    counts: dict[tuple, int] = {}
    for row in text.splitlines():
        block = BLOCK.match(row)
        if block is not None and int(block["end"]) >= int(block["start"]):
            key = block.group("file", "start", "from", "end", "to")
            counts[key] = max(counts.get(key, 0), int(block["count"]))
    ran: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for (name, start, _, end, _), count in counts.items():
        for number in range(int(start), int(end) + 1):
            best_and_missed = ran[name][number]
            best_and_missed[0] = max(best_and_missed[0], count)
            best_and_missed[1] += count == 0
    return Report("Go", {name: _lines_of(lines) for name, lines in ran.items()})


def _lines_of(blocks: dict[int, list[int]]) -> Lines:
    return {number: CoverageLine(hits, partial=hits > 0 and missed > 0) for number, (hits, missed) in blocks.items()}
