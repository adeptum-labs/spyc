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
from spyc.git.blame import BlameLine, parse_blame
from spyc.git.repository import Git

A = "a" * 40
B = "b" * 40
NOBODY = "0" * 40
SAMPLE = f"""\
{A} 1 1 2
author Ada
author-mail <ada@example.com>
author-time 1700000000
author-tz +0000
committer Ada
committer-mail <ada@example.com>
committer-time 1700000000
committer-tz +0000
summary First version
filename f.txt
\tone
{A} 2 2
\ttwo
{B} 3 3 1
author Bob
author-mail <bob@example.com>
author-time 1710000000
author-tz +0000
summary Add three
previous {A} f.txt
filename f.txt
\tthree
{NOBODY} 4 4 1
author Not Committed Yet
author-time 1720000000
summary Version of f.txt from f.txt
filename f.txt
\tfour
"""


def test_each_line_gets_the_details_of_its_commit():
    lines = parse_blame(SAMPLE)
    assert [(line.line, line.hash, line.author, line.timestamp, line.summary) for line in lines] == [
        (1, A, "Ada", 1700000000, "First version"),
        (2, A, "Ada", 1700000000, "First version"),
        (3, B, "Bob", 1710000000, "Add three"),
        (4, NOBODY, "Not Committed Yet", 1720000000, "Version of f.txt from f.txt")]
    assert [line.uncommitted for line in lines] == [False, False, False, True]


def test_a_line_with_a_tab_in_its_text_does_not_confuse_the_parser():
    assert len(parse_blame(f"{A} 1 1 1\nauthor Ada\nauthor-time 1\nsummary S\nfilename f\n\ta\tb\n")) == 1


def test_blame_follows_the_commits_and_the_uncommitted_edit(git_repo):
    write_files(git_repo, {"f.txt": "one\ntwo\nthree\n"})
    git(git_repo, "add", "f.txt")
    git(git_repo, "commit", "-qm", "Add f")
    (git_repo / "f.txt").write_text("one\nTWO\nthree\n")
    git(git_repo, "commit", "-qam", "Shout two")
    (git_repo / "f.txt").write_text("one\nTWO\nthree\nfour\n")
    lines = Git(git_repo).blame("f.txt")
    assert [line.uncommitted for line in lines] == [False, False, False, True]
    assert [line.summary for line in lines[:3]] == ["Add f", "Shout two", "Add f"]
    assert lines[0].author == "Test" and not lines[0].uncommitted and lines[3].uncommitted


def test_a_file_git_does_not_know_has_no_blame(git_repo):
    write_files(git_repo, {"new.py": "x\n"})
    assert Git(git_repo).blame("new.py") is None


def test_outside_a_repository_there_is_no_blame(tmp_path):
    (tmp_path / "a.txt").write_text("x\n")
    assert Git(tmp_path).blame("a.txt") is None


def test_blame_lines_can_be_compared():
    assert BlameLine(1, A, "Ada", 1, "S") == BlameLine(1, A, "Ada", 1, "S")
