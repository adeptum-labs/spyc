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

from repos import git, write_files
from spyc.git.log import Commit, parse_log
from spyc.git.repository import Git
from spyc.timeago import age


def commit(repo, name, content, message):
    write_files(repo, {name: content})
    git(repo, "add", name)
    git(repo, "commit", "-qm", message)


def test_commits_are_split_into_their_fields():
    output = "abc123\x1fabc\x1fAda\x1f1700000000\x1fHEAD -> main, tag: v1\x1fFix it\0def456\x1fdef\x1fBob\x1f1690000000\x1f\x1fAdd [x]\0"
    assert parse_log(output) == [
        Commit("abc123", "abc", "Ada", 1700000000, "HEAD -> main, tag: v1", "Fix it"),
        Commit("def456", "def", "Bob", 1690000000, "", "Add [x]")]


def test_a_subject_may_hold_the_separator_characters_of_git_output():
    assert parse_log("h\x1fs\x1fA\x1f1\x1f\x1fone\x1ftwo\0")[0].subject == "one\x1ftwo"


def test_commits_come_newest_first(git_repo):
    commit(git_repo, "a.txt", "a", "Add a")
    commit(git_repo, "b.txt", "b", "Add b")
    log = Git(git_repo).log()
    assert [entry.subject for entry in log] == ["Add b", "Add a", "Initial commit"]
    assert log[0].author == "Test" and len(log[0].short) < len(log[0].hash) and log[0].timestamp > 1_600_000_000
    assert "HEAD" in log[0].refs


def test_the_log_is_read_in_pages(git_repo):
    commit(git_repo, "a.txt", "a", "Add a")
    commit(git_repo, "b.txt", "b", "Add b")
    assert [entry.subject for entry in Git(git_repo).log(limit=2)] == ["Add b", "Add a"]
    assert [entry.subject for entry in Git(git_repo).log(limit=2, skip=2)] == ["Initial commit"]


def test_the_log_can_be_filtered_by_message_ignoring_case_and_regex_syntax(git_repo):
    commit(git_repo, "a.txt", "a", "Fix the [parser]")
    commit(git_repo, "b.txt", "b", "Add b")
    assert [entry.subject for entry in Git(git_repo).log(grep="[PARSER]")] == ["Fix the [parser]"]
    assert Git(git_repo).log(grep="nothing like this") == []


def test_the_history_of_one_file_follows_it_across_a_rename(git_repo):
    commit(git_repo, "old.txt", "first\nsecond\nthird\n", "Add old")
    commit(git_repo, "other.txt", "x", "Unrelated")
    git(git_repo, "mv", "old.txt", "new.txt")
    git(git_repo, "commit", "-qm", "Rename old to new")
    assert [entry.subject for entry in Git(git_repo).log(path="new.txt")] == ["Rename old to new", "Add old"]


def test_outside_a_repository_there_is_no_log(tmp_path):
    assert Git(tmp_path).log() is None


@pytest.mark.parametrize("seconds, expected", [
    (0, "now"), (59, "now"), (60, "1m"), (3599, "59m"), (3600, "1h"), (86399, "23h"), (86400, "1d"),
    (6 * 86400, "6d"), (7 * 86400, "1w"), (29 * 86400, "4w"), (30 * 86400, "1mo"), (364 * 86400, "12mo"),
    (365 * 86400, "1y"), (800 * 86400, "2y"), (-5, "now")])
def test_ages_are_short(seconds, expected):
    assert age(seconds) == expected


def test_a_commit_whose_fields_cannot_be_split_is_skipped_not_fatal():
    bad = "h\x1fs\x1fAda\x1fLovelace\x1f1\x1f\x1fsubject\0"
    good = "g\x1fg\x1fBob\x1f2\x1f\x1fSubject\0"
    assert [commit.hash for commit in parse_log(bad + good)] == ["g"]


def test_the_log_can_start_at_a_given_commit(git_repo):
    commit(git_repo, "a.txt", "a", "Add a")
    commit(git_repo, "b.txt", "b", "Add b")
    middle = Git(git_repo).log()[1].hash
    assert [entry.subject for entry in Git(git_repo).log(revision=middle)] == ["Add a", "Initial commit"]
