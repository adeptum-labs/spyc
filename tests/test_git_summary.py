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


from repos import git
from spyc.git.log import Commit
from spyc.git.repository import Git
from spyc.git.summary import GitSummary, summary_text

NOW = 1_700_100_000
LAST = Commit("a" * 40, "aaaaaaa", "Ada", 1_700_000_000, "", "Fix the parser")


def test_the_branch_is_named(git_repo):
    assert Git(git_repo).branch() == git(git_repo, "symbolic-ref", "--short", "HEAD").strip()


def test_a_branch_without_commits_is_still_named(tmp_path):
    git(tmp_path, "init", "-q", "-b", "trunk")
    assert Git(tmp_path).branch() == "trunk"


def test_a_detached_head_is_shown_by_its_commit(git_repo):
    git(git_repo, "checkout", "-q", "--detach")
    branch = Git(git_repo).branch()
    assert branch.startswith("(detached ") and branch.endswith(")")


def test_outside_a_repository_there_is_no_branch(tmp_path):
    assert Git(tmp_path).branch() is None


def test_the_summary_collects_branch_changes_and_last_commit(git_repo):
    (git_repo / "README.md").write_text("changed\n")
    summary = Git(git_repo).summary({"README.md": "M", "new.py": "?"})
    assert summary.changed == 2 and summary.last.subject == "Initial commit"
    assert summary.branch == Git(git_repo).branch()


def test_the_text_tells_branch_changes_and_last_commit():
    text = summary_text(GitSummary("main", 3, LAST), NOW).plain
    assert text == "main · 3 changed · last: aaaaaaa 1d Ada Fix the parser"


def test_a_clean_tree_and_an_empty_history_are_told_plainly():
    assert summary_text(GitSummary("main", 0, LAST), NOW).plain.startswith("main · clean · ")
    assert summary_text(GitSummary("main", 0, None), NOW).plain == "main · clean · no commits yet"
