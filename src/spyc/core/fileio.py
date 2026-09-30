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


import stat
from pathlib import Path


# A device or a pipe reports a size of zero and never ends, so the kind of file
# is checked before it is opened, and never more than the limit is read. A link
# to a regular file is followed; a link to /dev/zero is not read.
def read_limited(path: Path, limit: int) -> bytes | None:
    try:
        status = path.stat()
        if not stat.S_ISREG(status.st_mode) or status.st_size > limit:
            return None
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None
