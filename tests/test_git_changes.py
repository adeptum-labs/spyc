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


from repos import git, write_files
from spyc.git.changes import LineChanges, parse_hunks
from spyc.git.repository import Git

FIVE_LINES = "one\ntwo\nthree\nfour\nfive\n"


def test_added_lines_come_from_a_hunk_without_old_lines():
    assert parse_hunks("@@ -1,0 +2,2 @@\n+a\n+b\n") == LineChanges(added=frozenset({2, 3}))


def test_replaced_lines_are_modified_and_a_single_line_hunk_has_an_implied_count():
    assert parse_hunks("@@ -3 +3 @@\n-x\n+y\n@@ -7,2 +7,3 @@\n") == LineChanges(modified=frozenset({3, 7, 8, 9}))


def test_deleted_lines_are_marked_on_the_line_that_follows_them():
    assert parse_hunks("@@ -5,2 +4,0 @@\n-a\n-b\n") == LineChanges(deleted=frozenset({5}))
    assert parse_hunks("@@ -1 +0,0 @@\n-a\n") == LineChanges(deleted=frozenset({1}))


def test_text_that_only_looks_like_a_hunk_header_is_ignored():
    assert parse_hunks("+@@ -1 +1 @@\n context\n") == LineChanges()


def test_every_line_can_be_marked_as_added():
    assert LineChanges.everything(3) == LineChanges(added=frozenset({1, 2, 3}))


def test_changes_of_a_tracked_file_are_found(git_repo):
    write_files(git_repo, {"f.txt": FIVE_LINES})
    git(git_repo, "add", "f.txt")
    git(git_repo, "commit", "-qm", "Add f")
    (git_repo / "f.txt").write_text("one\nTWO\nthree\nfive\nsix\nseven\n")
    assert Git(git_repo).line_changes("f.txt") == LineChanges(
        added=frozenset({5, 6}), modified=frozenset({2}), deleted=frozenset({4}))


def test_staged_changes_count_too(git_repo):
    (git_repo / "README.md").write_text("# Project\n\nA test project.\nMore\n")
    git(git_repo, "add", "README.md")
    assert Git(git_repo).line_changes("README.md") == LineChanges(added=frozenset({4}))


def test_an_unchanged_file_has_no_changes(git_repo):
    assert Git(git_repo).line_changes("README.md") == LineChanges()


def test_before_the_first_commit_staged_lines_are_added(tmp_path):
    (tmp_path / "a.txt").write_text("x\ny\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "a.txt")
    assert Git(tmp_path).line_changes("a.txt") == LineChanges(added=frozenset({1, 2}))


def test_outside_a_repository_there_are_no_changes(tmp_path):
    (tmp_path / "a.txt").write_text("x\n")
    assert Git(tmp_path).line_changes("a.txt") is None
