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


import errno
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from spyc.core.languages import Language, detect_language
from spyc.core.printable import printable

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


def oversized(path: Path, size: int, mtime: float) -> Document:
    return Document(path, (), None, mtime, notice=f"File too large to show, {size:,} bytes")


def load_document(path: Path) -> Document:
    status = path.stat()
    if stat.S_ISDIR(status.st_mode):
        raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), str(path))
    if not stat.S_ISREG(status.st_mode):
        return Document(path, (), None, status.st_mtime, notice="Not a regular file")
    if status.st_size > FILE_LIMIT:
        return oversized(path, status.st_size, status.st_mtime)
    return document_of(path, path.read_bytes(), status.st_mtime)


def document_of(path: Path, data: bytes, mtime: float) -> Document:
    if b"\0" in data[:BINARY_PROBE]:
        return Document(path, (), None, mtime, notice=f"Binary file, {len(data):,} bytes")
    text = data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    lines = printable(text, keep_newlines=True).split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    plain = len(data) > HIGHLIGHT_LIMIT or any(len(line) > LONG_LINE for line in lines)
    return Document(path, tuple(lines), detect_language(path.name, lines[0]), mtime, plain=plain)
