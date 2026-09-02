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
from collections.abc import Sequence


def find_matches(lines: Sequence[str], query: str) -> list[tuple[int, int, int]]:
    if not query:
        return []
    pattern = re.compile(re.escape(query), 0 if any(char.isupper() for char in query) else re.IGNORECASE)
    return [(row, match.start(), match.end()) for row, line in enumerate(lines) for match in pattern.finditer(line)]
