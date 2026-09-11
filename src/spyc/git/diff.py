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
from dataclasses import dataclass, field

DIFF_LINE_LIMIT = 20_000
BINARY_PROBE = 8192
HUNK = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
NO_FILE = "/dev/null"


@dataclass(frozen=True)
class DiffLine:
    kind: str
    text: str
    old: int | None
    new: int | None


@dataclass
class FileDiff:
    path: str
    old_path: str
    status: str = "modified"
    lines: list[DiffLine] = field(default_factory=list)
    binary: bool = False
    additions: int = 0
    deletions: int = 0


@dataclass
class Diff:
    files: list[FileDiff] = field(default_factory=list)
    truncated: bool = False


def _paths_of_header(header: str) -> tuple[str, str]:
    old, _, new = header.removeprefix("diff --git ").removeprefix("a/").partition(" b/")
    return old.strip('"'), new.strip('"')


def _named(line: str, prefix: str) -> str | None:
    name = line[4:].rstrip("\t")
    return name.removeprefix(prefix) if name.startswith(prefix) else None


class _Parser:
    def __init__(self, limit: int) -> None:
        self.diff = Diff()
        self.limit = limit
        self.total = 0
        self.file: FileDiff | None = None
        self.in_hunk = False
        self.old = self.new = 0

    def feed(self, line: str) -> bool:
        if line.startswith("diff --git "):
            old, new = _paths_of_header(line)
            self.file = FileDiff(path=new, old_path=old)
            self.diff.files.append(self.file)
            self.in_hunk = False
        elif self.file is not None:
            return self._in_hunk(line) if self.in_hunk else self._in_header(line)
        return True

    def _in_header(self, line: str) -> bool:
        file = self.file
        if line.startswith("@@"):
            self.in_hunk = True
            return self._in_hunk(line)
        if line.startswith("new file mode"):
            file.status = "added"
        elif line.startswith("deleted file mode"):
            file.status = "deleted"
        elif line.startswith("rename from "):
            file.old_path, file.status = line.removeprefix("rename from "), "renamed"
        elif line.startswith("rename to "):
            file.path = line.removeprefix("rename to ")
        elif line.startswith(("Binary files", "GIT binary patch")):
            file.binary = True
        elif line.startswith("--- "):
            file.old_path = _named(line, "a/") or file.old_path
        elif line.startswith("+++ "):
            file.path = _named(line, "b/") or file.path
        return True

    def _in_hunk(self, line: str) -> bool:
        header = HUNK.match(line)
        if header:
            self.old, self.new = int(header["old"]), int(header["new"])
            return self._append(DiffLine("hunk", line, None, self.new))
        if line.startswith("+"):
            self.file.additions += 1
            self.new += 1
            return self._append(DiffLine("add", line[1:], None, self.new - 1))
        if line.startswith("-"):
            self.file.deletions += 1
            self.old += 1
            return self._append(DiffLine("delete", line[1:], self.old - 1, None))
        if line.startswith(" "):
            self.old, self.new = self.old + 1, self.new + 1
            return self._append(DiffLine("context", line[1:], self.old - 1, self.new - 1))
        if line.startswith("\\"):
            return self._append(DiffLine("note", line[2:], None, None))
        self.in_hunk = False
        return True

    def _append(self, line: DiffLine) -> bool:
        if self.total >= self.limit:
            self.diff.truncated = True
            return False
        self.file.lines.append(line)
        self.total += 1
        return True


def parse_diff(text: str, limit: int = DIFF_LINE_LIMIT) -> Diff:
    parser = _Parser(limit)
    for line in text.split("\n"):
        if not parser.feed(line):
            break
    return parser.diff


def diff_of_new_file(path: str, data: bytes) -> FileDiff:
    if b"\0" in data[:BINARY_PROBE]:
        return FileDiff(path, path, "added", binary=True)
    lines = data.decode("utf-8", errors="replace").split("\n")
    if lines[-1] == "":
        lines.pop()
    file = FileDiff(path, path, "added", additions=len(lines))
    if lines:
        file.lines.append(DiffLine("hunk", f"@@ -0,0 +1,{len(lines)} @@", None, 1))
        file.lines.extend(DiffLine("add", text, None, number) for number, text in enumerate(lines, 1))
    return file
