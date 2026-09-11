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

GROUP_HEADER = re.compile(r"^(?P<hash>[0-9a-f]{40}) \d+ (?P<line>\d+)(?: \d+)?$")
NOT_COMMITTED = "0" * 40


@dataclass(frozen=True)
class BlameLine:
    line: int
    hash: str
    author: str
    timestamp: int
    summary: str

    @property
    def uncommitted(self) -> bool:
        return self.hash == NOT_COMMITTED


# In git's porcelain format the details of a commit come only with the first
# of its lines that is shown, so they are kept and given to the lines after it.
def parse_blame(output: str) -> list[BlameLine]:
    commits: dict[str, dict[str, str]] = {}
    lines: list[BlameLine] = []
    header = None
    for text in output.split("\n"):
        if text.startswith("\t"):
            if header is not None:
                details = commits.get(header["hash"], {})
                lines.append(BlameLine(int(header["line"]), header["hash"], details.get("author", ""),
                                       int(details.get("author-time", 0)), details.get("summary", "")))
            header = None
            continue
        matched = GROUP_HEADER.match(text)
        if matched:
            header = matched
            commits.setdefault(matched["hash"], {})
        elif header is not None:
            key, _, value = text.partition(" ")
            if key in ("author", "author-time", "summary"):
                commits[header["hash"]][key] = value
    return lines
