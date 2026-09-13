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
from spyc.git.diff import DiffLine, FileDiff, diff_of_new_file, parse_diff
from spyc.git.repository import Git

MODIFIED = """\
diff --git a/a.txt b/a.txt
index 111..222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,3 @@ def f
 one
-two
+TWO
 three
"""


def test_a_modified_file_is_split_into_numbered_lines():
    (file,) = parse_diff(MODIFIED).files
    assert (file.path, file.old_path, file.status, file.additions, file.deletions) == ("a.txt", "a.txt", "modified", 1, 1)
    assert file.lines == [
        DiffLine("hunk", "@@ -1,3 +1,3 @@ def f", None, 1),
        DiffLine("context", "one", 1, 1),
        DiffLine("delete", "two", 2, None),
        DiffLine("add", "TWO", None, 2),
        DiffLine("context", "three", 3, 3)]


def test_new_deleted_and_renamed_files_have_their_status():
    text = ("diff --git a/n.txt b/n.txt\nnew file mode 100644\nindex 0..1\n--- /dev/null\n+++ b/n.txt\n@@ -0,0 +1,2 @@\n+a\n+b\n"
            "diff --git a/d.txt b/d.txt\ndeleted file mode 100644\nindex 1..0\n--- a/d.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
            "diff --git a/old.txt b/new.txt\nsimilarity index 100%\nrename from old.txt\nrename to new.txt\n")
    added, deleted, renamed = parse_diff(text).files
    assert (added.path, added.status, added.additions) == ("n.txt", "added", 2)
    assert (deleted.path, deleted.status, deleted.deletions) == ("d.txt", "deleted", 1)
    assert (renamed.path, renamed.old_path, renamed.status, renamed.lines) == ("new.txt", "old.txt", "renamed", [])


def test_binary_files_have_no_lines():
    text = "diff --git a/x.png b/x.png\nindex 1..2 100644\nBinary files a/x.png and b/x.png differ\n"
    (file,) = parse_diff(text).files
    assert file.binary and file.lines == []


def test_the_no_newline_marker_is_a_line_without_numbers():
    text = MODIFIED + "\\ No newline at end of file\n"
    assert parse_diff(text).files[0].lines[-1] == DiffLine("note", "No newline at end of file", None, None)


def test_a_path_with_spaces_loses_the_tab_git_puts_after_it():
    text = "diff --git a/with space.py b/with space.py\n--- a/with space.py\t\n+++ b/with space.py\t\n@@ -1 +1 @@\n-a\n+b\n"
    assert parse_diff(text).files[0].path == "with space.py"


def test_long_diffs_are_cut_and_say_so():
    text = MODIFIED + "".join(f"+line {number}\n" for number in range(50))
    result = parse_diff(text, limit=10)
    assert result.truncated and sum(len(file.lines) for file in result.files) == 10


def test_a_new_file_that_is_not_tracked_yet_is_shown_as_added():
    file = diff_of_new_file("n.py", b"a\nb\n")
    assert (file.path, file.status, file.additions) == ("n.py", "added", 2)
    assert file.lines == [DiffLine("hunk", "@@ -0,0 +1,2 @@", None, 1), DiffLine("add", "a", None, 1), DiffLine("add", "b", None, 2)]
    assert diff_of_new_file("blob", b"\0\1\2").binary


def test_a_commit_comes_with_its_message_and_its_diff(git_repo):
    write_files(git_repo, {"a.txt": "one\ntwo\n"})
    git(git_repo, "add", "a.txt")
    git(git_repo, "commit", "-qm", "Add a\n\nWith a longer explanation.")
    head = Git(git_repo).log(limit=1)[0]
    detail = Git(git_repo).commit_detail(head.hash)
    assert detail.message.startswith("Add a\n\nWith a longer explanation.")
    assert [(file.path, file.status) for file in detail.diff.files] == [("a.txt", "added")]


def test_the_first_commit_can_be_shown_too(git_repo):
    first = Git(git_repo).log()[-1]
    assert {file.path for file in Git(git_repo).commit_detail(first.hash).diff.files} >= {"README.md"}


def test_the_working_tree_diff_covers_staged_unstaged_and_untracked_files(git_repo):
    (git_repo / "README.md").write_text("# Project\n\nchanged\n")
    write_files(git_repo, {"new.py": "x = 1\n", "staged.py": "y = 2\n"})
    git(git_repo, "add", "staged.py")
    diff = Git(git_repo).working_diff(["new.py"])
    assert {(file.path, file.status) for file in diff.files} == {
        ("README.md", "modified"), ("staged.py", "added"), ("new.py", "added")}


def test_outside_a_repository_there_is_no_diff(tmp_path):
    assert Git(tmp_path).working_diff([]) is None
    assert Git(tmp_path).commit_detail("abc") is None


def test_untracked_links_and_pipes_are_not_followed(git_repo, tmp_path):
    import os
    (tmp_path / "outside.txt").write_text("secret\n")
    (git_repo / "link").symlink_to(tmp_path / "outside.txt")
    os.mkfifo(git_repo / "pipe")
    write_files(git_repo, {"real.py": "x = 1\n"})
    diff = Git(git_repo).working_diff(["link", "pipe", "real.py"])
    assert [file.path for file in diff.files] == ["real.py"]


def test_untracked_files_stop_at_the_line_limit_and_the_diff_says_so(git_repo, monkeypatch):
    monkeypatch.setattr("spyc.git.repository.DIFF_LINE_LIMIT", 15)
    write_files(git_repo, {name: "line\n" * 10 for name in ("a.py", "b.py", "c.py")})
    diff = Git(git_repo).working_diff(["a.py", "b.py", "c.py"])
    assert diff.truncated and sum(len(file.lines) for file in diff.files) == 15
    assert [file.path for file in diff.files] == ["a.py", "b.py"]
