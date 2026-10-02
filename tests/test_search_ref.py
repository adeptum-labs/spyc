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
from spyc.core.cancellation import Cancellation
from spyc.git.ref_source import GitRefSource
from spyc.git.repository import Git
from spyc.search import search_text


@pytest.fixture
def source(tmp_path):
    root = make_repo(tmp_path / "p", {"a.py": "def foo():\n    return 1\n"})
    git(root, "checkout", "-q", "-b", "feature")
    write_files(root, {"a.py": "def foo():\n    return Foo\n", "sub/c.txt": "é foo\nfoobar\n", "sp ace.txt": "foo bar\n"})
    (root / "bin.dat").write_bytes(b"foo\0bar")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "More")
    git(root, "checkout", "-q", "-")
    source = GitRefSource(Git(root), git(root, "rev-parse", "feature").strip(), "feature")
    yield source
    source.close()


def look(source, query, **options):
    return search_text(source.root, (), query, source=source, **options)


def places(result):
    return [(hit.path, hit.line, hit.column) for hit in result.hits]


def test_the_branch_is_searched_not_the_working_tree(source):
    assert ("sub/c.txt", 1, 2) in places(look(source, "foo"))
    assert not (source.root / "sub").exists()


def test_case_is_ignored_unless_the_query_has_a_capital(source):
    assert ("a.py", 2, 11) in places(look(source, "foo"))
    assert places(look(source, "Foo")) == [("a.py", 2, 11)]


def test_the_column_counts_characters_not_bytes(source):
    assert ("sub/c.txt", 1, 2) in places(look(source, "foo"))


def test_whole_word_skips_longer_words(source):
    assert ("sub/c.txt", 2, 0) not in places(look(source, "foo", whole_word=True))
    assert ("sub/c.txt", 2, 0) in places(look(source, "foo"))


def test_a_pattern_is_allowed_because_git_can_be_interrupted(source):
    assert places(look(source, r"fo+bar", regex=True)) == [("sub/c.txt", 2, 0)]


def test_a_bad_pattern_is_reported(source):
    assert look(source, "(", regex=True).error.startswith("Bad pattern")


def test_binary_files_are_skipped_and_paths_with_spaces_found(source):
    found = places(look(source, "foo"))
    assert not any(path == "bin.dat" for path, _, _ in found)
    assert ("sp ace.txt", 1, 0) in found


def test_the_hits_are_cut_at_the_limit(source):
    result = look(source, "foo", limit=2)
    assert len(result.hits) == 2 and result.truncated


def test_no_hits_is_not_an_error(source):
    result = look(source, "nothing like this")
    assert result.hits == [] and result.error is None


def test_a_cancelled_search_gives_nothing(source):
    cancellation = Cancellation()
    cancellation.cancel()
    assert look(source, "foo", cancellation=cancellation).hits == []
