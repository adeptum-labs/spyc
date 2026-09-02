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
from pathlib import Path

from spyc.languages import Language, detect_language

FILE_LIMIT = 50 * 1024 * 1024
HIGHLIGHT_LIMIT = 2 * 1024 * 1024
LONG_LINE = 10_000
BINARY_PROBE = 8192


@dataclass(frozen=True)
class Document:
    path: Path
    lines: tuple[str, ...]
    language: Language | None
    mtime: float
    notice: str | None = None
    plain: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def load_document(path: Path) -> Document:
    status = path.stat()
    if status.st_size > FILE_LIMIT:
        return Document(path, (), None, status.st_mtime, notice=f"File too large to show, {status.st_size:,} bytes")
    data = path.read_bytes()
    if b"\0" in data[:BINARY_PROBE]:
        return Document(path, (), None, status.st_mtime, notice=f"Binary file, {len(data):,} bytes")
    lines = [line.removesuffix("\r") for line in data.decode("utf-8-sig", errors="replace").split("\n")]
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    plain = len(data) > HIGHLIGHT_LIMIT or any(len(line) > LONG_LINE for line in lines)
    return Document(path, tuple(lines), detect_language(path.name, lines[0]), status.st_mtime, plain=plain)
