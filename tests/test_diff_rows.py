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


from spyc.diff_rows import DiffRow, location_of, rows_of
from spyc.git.diff import Diff, DiffLine, FileDiff

MODIFIED = FileDiff("a.txt", "a.txt", "modified", [
    DiffLine("hunk", "@@ -1,3 +1,3 @@", None, 1),
    DiffLine("context", "one", 1, 1),
    DiffLine("delete", "two", 2, None),
    DiffLine("add", "TWO", None, 2),
    DiffLine("context", "three", 3, 3)], additions=1, deletions=1)
RENAMED = FileDiff("new.txt", "old.txt", "renamed")
BINARY = FileDiff("x.png", "x.png", "added", binary=True)


def test_rows_start_with_the_message_then_list_each_file():
    rows = rows_of("Subject\n\nBody", Diff([MODIFIED]))
    assert [(row.kind, row.text) for row in rows[:5]] == [
        ("message", "Subject"), ("message", ""), ("message", "Body"), ("message", ""),
        ("file", "modified a.txt  +1 -1")]
    assert [row.kind for row in rows[5:]] == ["hunk", "context", "delete", "add", "context", "blank"]
    assert all(row.path == "a.txt" for row in rows[4:])


def test_a_diff_without_a_message_starts_with_the_first_file():
    assert rows_of(None, Diff([MODIFIED]))[0].kind == "file"


def test_renamed_and_binary_files_are_described():
    rows = rows_of(None, Diff([RENAMED, BINARY]))
    assert rows[0].text == "renamed old.txt -> new.txt  +0 -0"
    assert [(row.kind, row.text) for row in rows if row.kind == "note"] == [("note", "Binary file")]


def test_a_cut_diff_says_so():
    assert rows_of(None, Diff([MODIFIED], truncated=True))[-1] == DiffRow("info", "The diff is cut here")


def test_each_row_opens_the_line_it_shows():
    rows = rows_of(None, Diff([MODIFIED]))
    kinds = {row.kind: index for index, row in enumerate(rows)}
    assert location_of(rows, 0) == ("a.txt", 1)
    assert location_of(rows, kinds["context"]) == ("a.txt", 3)
    assert location_of(rows, kinds["add"]) == ("a.txt", 2)
    assert location_of(rows, kinds["hunk"]) == ("a.txt", 1)


def test_a_deleted_line_opens_the_line_that_follows_it_and_message_rows_open_nothing():
    rows = rows_of("Subject", Diff([MODIFIED]))
    delete = next(index for index, row in enumerate(rows) if row.kind == "delete")
    assert location_of(rows, delete) == ("a.txt", 2)
    assert location_of(rows, 0) is None


def test_a_deleted_file_opens_nothing():
    gone = FileDiff("d.txt", "d.txt", "deleted", [DiffLine("hunk", "@@ -1 +0,0 @@", None, 1), DiffLine("delete", "x", 1, None)])
    assert [location_of(rows_of(None, Diff([gone])), index) for index in range(3)] == [None, None, None]
