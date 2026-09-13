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

FIELD_SEPARATOR = "\x1f"
LOG_FORMAT = "%x1f".join(["%H", "%h", "%an", "%at", "%D", "%s"])


@dataclass(frozen=True)
class Commit:
    hash: str
    short: str
    author: str
    timestamp: int
    refs: str
    subject: str


# The subject is the last field, so a separator inside it stays in the subject.
def parse_log(output: str) -> list[Commit]:
    commits = []
    for entry in filter(None, output.split("\0")):
        try:
            full, short, author, timestamp, refs, subject = entry.strip("\n").split(FIELD_SEPARATOR, 5)
            commits.append(Commit(full, short, author, int(timestamp), refs, subject))
        except ValueError:
            continue
    return commits
