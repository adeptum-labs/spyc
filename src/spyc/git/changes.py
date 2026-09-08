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

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(?P<old>\d+))? \+(?P<start>\d+)(?:,(?P<new>\d+))? @@", re.MULTILINE)


# Line numbers are 1-based lines of the file as it is now. A deletion has no
# line of its own, so it is marked on the line that follows the removed text.
@dataclass(frozen=True)
class LineChanges:
    added: frozenset[int] = frozenset()
    modified: frozenset[int] = frozenset()
    deleted: frozenset[int] = frozenset()

    @classmethod
    def everything(cls, line_count: int) -> "LineChanges":
        return cls(added=frozenset(range(1, line_count + 1)))


def parse_hunks(diff: str) -> LineChanges:
    added: set[int] = set()
    modified: set[int] = set()
    deleted: set[int] = set()
    for hunk in HUNK_HEADER.finditer(diff):
        old = int(hunk["old"]) if hunk["old"] is not None else 1
        start = int(hunk["start"])
        new = int(hunk["new"]) if hunk["new"] is not None else 1
        if new == 0:
            deleted.add(start + 1)
        else:
            (added if old == 0 else modified).update(range(start, start + new))
    return LineChanges(frozenset(added), frozenset(modified), frozenset(deleted))
