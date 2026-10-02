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
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from spyc.core.document import FILE_LIMIT, Document, document_of, oversized
from spyc.core.file_index import FileIndex
from spyc.core.source import FileStamp
from spyc.git.repository import Git, git_environment

READ_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class TreeEntry:
    oid: str
    size: int


# Only blobs are files: a submodule is listed as a commit and has no content here.
# A link is a blob too, and its content is the path it points to.
def parse_tree(output: str) -> dict[str, TreeEntry]:
    entries = {}
    for record in filter(None, output.split("\0")):
        meta, _, path = record.partition("\t")
        fields = meta.split()
        if len(fields) == 4 and fields[1] == "blob":
            entries[path] = TreeEntry(fields[2], int(fields[3]))
    return entries


# The files of one commit, read with git alone: the working tree, the index and
# HEAD are never touched, and the commit is fixed so that the view cannot move
# when the branch does. The contents come through one long-lived `cat-file
# --batch`, which is started when first needed and again if it dies.
class GitRefSource:
    editable = False

    def __init__(self, git: Git, commit: str, ref: str) -> None:
        self._git, self.root, self.commit, self.ref = Git(git.root, offline=True), git.root, commit, ref
        self._entries: dict[str, TreeEntry] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def list_files(self, show_ignored: bool, limit: int) -> FileIndex:
        paths = sorted(self._tree())
        return FileIndex(self.root, tuple(paths[:limit]), truncated=len(paths) > limit)

    def read(self, path: str, limit: int) -> bytes | None:
        entry = self._tree().get(path)
        return None if entry is None or entry.size > limit else self._blob(entry.oid)

    def stamp(self, path: str) -> FileStamp | None:
        entry = self._tree().get(path)
        return None if entry is None else FileStamp((entry.oid,), entry.size)

    def document(self, path: str) -> Document:
        entry = self._tree().get(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)
        if entry.size > FILE_LIMIT:
            return oversized(Path(path), entry.size, 0.0)
        data = self._blob(entry.oid)
        if data is None:
            raise OSError(errno.EIO, "Could not read the file from git", path)
        return document_of(Path(path), data, 0.0)

    def close(self) -> None:
        with self._lock:
            self._stop()

    # The listing runs outside the lock: it can take seconds on a big repository,
    # and whoever wants to close the source or read a file must not wait for it.
    def _tree(self) -> dict[str, TreeEntry]:
        with self._lock:
            entries = self._entries
        if entries is None:
            output = self._git.run("ls-tree", "-r", "-l", "-z", "--full-tree", self.commit)
            if output is None:
                return {}
            entries = parse_tree(output)
            with self._lock:
                self._entries = entries
        return entries

    # A reader that stops answering is killed after a while, so that a stalled git
    # cannot hold the lock, and with it the interface, for good.
    def _blob(self, oid: str) -> bytes | None:
        with self._lock:
            for _ in range(2):
                watchdog = threading.Timer(READ_TIMEOUT_SECONDS, self._kill)
                watchdog.start()
                try:
                    return self._request(oid)
                except (OSError, ValueError):
                    self._stop()
                finally:
                    watchdog.cancel()
        return None

    def _kill(self) -> None:
        process = self._process
        if process is not None:
            process.kill()

    def _request(self, oid: str) -> bytes | None:
        if self._process is None:
            self._process = subprocess.Popen(["git", "-C", str(self.root), "cat-file", "--batch"],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             env=git_environment(offline=True))
        process = self._process
        process.stdin.write(f"{oid}\n".encode())
        process.stdin.flush()
        header = process.stdout.readline().split()
        if header[1:] == [b"missing"]:
            return None
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError("unexpected answer from git")
        size = int(header[2])
        data = process.stdout.read(size)
        if len(data) != size:
            raise OSError(errno.EPIPE, "git stopped answering")
        process.stdout.read(1)
        return data

    def _stop(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        process.kill()
        # A reader that died is the usual reason to stop it, and closing its pipes then fails.
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except OSError:
                pass
        process.wait()
