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


import subprocess

import pytest

from repos import git, write_files
from spyc.git.changes import LineChanges
from spyc.git.repository import Git

HOSTILE_SETTINGS = [
    ("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true"), ("color.diff", "always"), ("color.ui", "always"),
    ("diff.suppressBlankEmpty", "true"), ("core.quotepath", "true")]


@pytest.fixture(params=HOSTILE_SETTINGS, ids=lambda pair: f"{pair[0]}={pair[1]}")
def hostile_repo(request, git_repo):
    write_files(git_repo, {"a.txt": "a\n\nb\nc\n"})
    git(git_repo, "add", "a.txt")
    git(git_repo, "commit", "-qm", "Add a")
    git(git_repo, "config", *request.param)
    return git_repo


def test_a_commit_diff_reads_the_same_whatever_the_users_diff_settings(hostile_repo):
    head = Git(hostile_repo).log(limit=1)[0]
    (file,) = Git(hostile_repo).commit_detail(head.hash).diff.files
    assert (file.path, file.status, file.additions) == ("a.txt", "added", 4)


def test_the_working_tree_diff_survives_the_users_diff_settings(hostile_repo):
    (hostile_repo / "a.txt").write_text("A\n\nb\nC\n")
    (file,) = Git(hostile_repo).working_diff([]).files
    assert (file.path, file.additions, file.deletions) == ("a.txt", 2, 2)
    assert [line.kind for line in file.lines].count("context") == 2


def test_the_change_marks_survive_the_users_diff_settings(hostile_repo):
    (hostile_repo / "a.txt").write_text("A\n\nb\nC\n")
    assert Git(hostile_repo).line_changes("a.txt") == LineChanges(modified=frozenset({1, 4}))


def test_the_log_and_show_never_print_signature_checks(monkeypatch, git_repo):
    commands = []
    real = subprocess.run
    monkeypatch.setattr("spyc.git.repository.subprocess.run", lambda command, **options: commands.append(command) or real(command, **options))
    Git(git_repo).log(limit=1)
    assert "log.showSignature=false" in commands[0]


def test_a_path_that_looks_like_a_glob_is_taken_literally(git_repo):
    write_files(git_repo, {"pages/[id].tsx": "a\n", "pages/i.tsx": "b\n"})
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-qm", "Add pages")
    write_files(git_repo, {"pages/i.tsx": "b\nmore\n"})
    git(git_repo, "commit", "-qam", "Touch i")
    (git_repo / "pages" / "[id].tsx").write_text("a\nx\n")
    assert [entry.subject for entry in Git(git_repo).log(path="pages/[id].tsx")] == ["Add pages"]
    assert Git(git_repo).line_changes("pages/[id].tsx") == LineChanges(added=frozenset({2}))


def test_blame_survives_an_ignore_file_setting_that_names_a_missing_file(git_repo):
    git(git_repo, "config", "blame.ignoreRevsFile", ".git-blame-ignore-revs")
    assert len(Git(git_repo).blame("README.md")) == 3
