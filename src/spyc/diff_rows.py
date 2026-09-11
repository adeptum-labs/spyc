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

from spyc.git.diff import Diff, FileDiff

LINE_KINDS = ("hunk", "context", "add")


# One line of the diff view: a line of the commit message, a file heading, a
# line of a hunk, or a note. `path` is where the row opens a file; a file that
# was deleted has none, since there is nothing left to open.
@dataclass(frozen=True)
class DiffRow:
    kind: str
    text: str
    old: int | None = None
    new: int | None = None
    path: str | None = None


def _title(file: FileDiff) -> str:
    name = f"{file.old_path} -> {file.path}" if file.status == "renamed" else file.path
    return f"{file.status} {name}  +{file.additions} -{file.deletions}"


def rows_of(message: str | None, diff: Diff) -> list[DiffRow]:
    rows: list[DiffRow] = []
    if message:
        rows.extend(DiffRow("message", line) for line in message.split("\n"))
        rows.append(DiffRow("message", ""))
    for file in diff.files:
        path = None if file.status == "deleted" else file.path
        rows.append(DiffRow("file", _title(file), new=None if path is None else 1, path=path))
        if file.binary:
            rows.append(DiffRow("note", "Binary file", path=path))
        rows.extend(DiffRow(line.kind, line.text, line.old, line.new, path) for line in file.lines)
        rows.append(DiffRow("blank", "", path=path))
    if diff.truncated:
        rows.append(DiffRow("info", "The diff is cut here"))
    return rows


def location_of(rows: list[DiffRow], index: int) -> tuple[str, int] | None:
    row = rows[index]
    if row.path is None:
        return None
    if row.kind == "file":
        return row.path, 1
    if row.kind in LINE_KINDS and row.new is not None:
        return row.path, row.new
    following = (candidate for candidate in rows[index + 1:] if candidate.path == row.path)
    preceding = (candidate for candidate in reversed(rows[:index]) if candidate.path == row.path)
    for candidate in (*following, *preceding):
        if candidate.kind in LINE_KINDS and candidate.new is not None:
            return row.path, candidate.new
    return row.path, 1
