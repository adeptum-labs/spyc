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


import pytest

from repos import git, make_repo, write_files
from spyc.git.branches import Branch, default_base, parse_branches
from spyc.git.repository import Git

SEP = "\x1f"


def record(ref, commit="a" * 40, upstream="", when=100, author="T", head=" ", subject="s"):
    return SEP.join([ref, commit, upstream, str(when), author, head, subject]) + "\0\n"


def branch(name, current=False):
    return Branch(name, name, name.startswith("origin/"), "c", "s", "a", 1, "", current)


def test_local_and_remote_branches_are_parsed_and_the_remote_head_is_left_out():
    output = (record("refs/heads/feature/x", head="*", subject="a\x1fb") + record("refs/remotes/origin/feature/x")
              + record("refs/remotes/origin/HEAD"))
    branches = parse_branches(output)
    assert [(b.name, b.remote, b.current) for b in branches] == [("feature/x", False, True), ("origin/feature/x", True, False)]
    assert branches[0].subject == "a\x1fb" and branches[0].timestamp == 100


def test_a_damaged_record_is_skipped():
    assert [b.name for b in parse_branches("junk\0\n" + record("refs/heads/ok"))] == ["ok"]


@pytest.mark.parametrize("names, origin_head, current, expected", [
    (["main", "master", "feature"], "origin/main", "feature", "main"),
    (["master", "main"], None, "master", "master"),
    (["main", "feature"], None, "feature", "main"),
    (["feature", "origin/master"], None, "feature", "origin/master"),
    (["feature", "origin/trunk"], "origin/trunk", "feature", "origin/trunk"),
    (["feature", "other"], None, "feature", "feature"),
])
def test_the_base_is_the_default_branch_or_else_the_current_one(names, origin_head, current, expected):
    branches = [branch(name, name == current) for name in names]
    assert default_base(branches, origin_head).name == expected


def test_no_branches_means_no_base():
    assert default_base([], None) is None


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path / "p", {"a.py": "line one\nline two\n"})
    git(root, "branch", "-m", "master")
    git(root, "checkout", "-q", "-b", "feature/x")
    write_files(root, {"a.py": "line one\nline 2\n", "new.txt": "n\n"})
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Change line two")
    git(root, "checkout", "-q", "master")
    write_files(root, {"other.txt": "o\n"})
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Move master on")
    return root


def test_the_repository_lists_its_branches_with_the_current_one_marked(repo):
    branches = {b.name: b for b in Git(repo).branches()}
    assert sorted(branches) == ["feature/x", "master"]
    assert (branches["master"].current, branches["feature/x"].current) == (True, False)
    assert branches["feature/x"].subject == "Change line two" and branches["feature/x"].author == "Test"


def test_ahead_and_behind_count_against_the_base(repo):
    assert Git(repo).ahead_behind("master", "feature/x") == (1, 1)
    assert Git(repo).ahead_behind("master", "master") == (0, 0)
    assert Git(repo).ahead_behind("master", "nope") is None


def test_the_branch_diff_shows_only_what_the_branch_changed(repo):
    diff = Git(repo).branch_diff("master", "feature/x")
    assert sorted(file.path for file in diff.files) == ["a.py", "new.txt"]


def test_without_a_remote_there_is_no_origin_head(repo):
    assert Git(repo).origin_head() is None


def test_blame_can_look_at_a_branch(repo):
    lines = Git(repo).blame("a.py", "feature/x")
    assert [line.summary for line in lines] == ["Initial commit", "Change line two"]
    assert [line.summary for line in Git(repo).blame("a.py")] == ["Initial commit", "Initial commit"]
