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


import os
from pathlib import Path

import pytest

from repos import git, make_repo, write_files
from spyc.git.ref_source import GitRefSource, TreeEntry, parse_tree
from spyc.git.repository import Git


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path / "project", {"a.py": "def foo():\n    return 1\n", "sub/b.txt": "one\n",
                                            "data.bin": "x"})
    (root / "data.bin").write_bytes(b"x\0y")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Binary")
    git(root, "checkout", "-q", "-b", "feature")
    write_files(root, {"a.py": "def foo():\n    return 2\n", "sub/c.txt": "new\n", "sp ace é.txt": "odd\n"})
    os.symlink("a.py", root / "link")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Change a and add files")
    git(root, "checkout", "-q", "-")
    return root


@pytest.fixture
def source(repo):
    source = GitRefSource(Git(repo), git(repo, "rev-parse", "feature").strip(), "feature")
    yield source
    source.close()


def test_it_lists_the_files_of_the_branch_not_of_the_working_tree(source):
    assert source.list_files(False, 100).paths == ("a.py", "data.bin", "link", "sp ace é.txt", "sub/b.txt", "sub/c.txt")


def test_the_list_is_cut_at_the_limit(source):
    index = source.list_files(False, 2)
    assert len(index.paths) == 2 and index.truncated


def test_it_reads_the_content_of_the_branch(source, repo):
    assert source.read("a.py", 100) == b"def foo():\n    return 2\n"
    assert (repo / "a.py").read_text() == "def foo():\n    return 1\n"
    assert source.read("a.py", 5) is None
    assert source.read("missing", 100) is None
    assert source.read("sp ace é.txt", 100) == b"odd\n"


def test_the_stamp_is_the_blob_so_equal_files_of_two_branches_share_it(source, repo):
    master = git(repo, "rev-parse", "master:sub/b.txt").strip()
    assert source.stamp("sub/b.txt").token == (master,)
    assert source.stamp("a.py").token != (git(repo, "rev-parse", "master:a.py").strip(),)
    assert source.stamp("missing") is None


def test_a_document_has_no_mtime_and_a_relative_path(source):
    document = source.document("a.py")
    assert document.lines == ("def foo():", "    return 2") and document.mtime == 0.0
    assert document.path == Path("a.py") and document.language.id == "python"
    assert source.document("data.bin").notice.startswith("Binary file")


def test_a_symlink_shows_where_it_points(source):
    assert source.document("link").lines == ("a.py",)


def test_a_missing_file_is_a_file_not_found_error(source):
    with pytest.raises(FileNotFoundError):
        source.document("nope.py")


def test_submodules_are_not_files():
    output = "160000 commit abc       -\tmod\x00100644 blob def      3\ta.py\x00"
    assert parse_tree(output) == {"a.py": TreeEntry("def", 3)}


def test_reading_leaves_the_repository_untouched(source, repo):
    def snapshot():
        return (git(repo, "status", "--porcelain=v2", "--branch"), git(repo, "rev-parse", "HEAD"),
                (repo / ".git" / "index").read_bytes(), sorted(p.name for p in (repo / ".git").iterdir()))

    before = snapshot()
    source.list_files(False, 100)
    source.read("a.py", 100)
    source.document("sub/c.txt")
    assert snapshot() == before


def test_a_reader_that_died_is_started_again(source):
    assert source.read("a.py", 100) is not None
    source._process.kill()
    source._process.wait()
    assert source.read("a.py", 100) == b"def foo():\n    return 2\n"
