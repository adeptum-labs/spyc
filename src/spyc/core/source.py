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
from typing import Protocol

from spyc.core.document import Document, load_document
from spyc.core.file_index import FileIndex, build_index
from spyc.core.fileio import read_limited


@dataclass(frozen=True)
class FileStamp:
    token: tuple[int | str, ...]
    size: int


# Where the files of the project come from: the working tree, or the commit of a
# branch. Every method may block, so the application calls them from workers.
class FileSource(Protocol):
    root: Path
    ref: str | None
    commit: str | None
    editable: bool

    def list_files(self, show_ignored: bool, limit: int) -> FileIndex: ...

    def read(self, path: str, limit: int) -> bytes | None: ...

    def stamp(self, path: str) -> FileStamp | None: ...

    def document(self, path: str) -> Document: ...


class DiskSource:
    ref = commit = None
    editable = True

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_files(self, show_ignored: bool, limit: int) -> FileIndex:
        return build_index(self.root, show_ignored, limit)

    def read(self, path: str, limit: int) -> bytes | None:
        return read_limited(self.root / path, limit)

    def stamp(self, path: str) -> FileStamp | None:
        try:
            status = (self.root / path).stat()
        except OSError:
            return None
        return FileStamp((status.st_mtime_ns, status.st_size), status.st_size)

    def document(self, path: str) -> Document:
        return load_document(self.root / path)
