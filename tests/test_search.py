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


import shutil

import pytest

from repos import git, make_repo, write_files
from spyc.file_index import build_index
from spyc.search import Hit, search_text

BACKENDS = [pytest.param(True, marks=pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")),
            False]
FILES = {"a.py": "def foo():\n    return Foo\n", "b.txt": "nothing\nfoo bar\nfoobar\n", "sub/c.py": "FOO = 1\n",
         "é.txt": "é foo\n"}


@pytest.fixture
def project(tmp_path):
    write_files(tmp_path, FILES)
    return tmp_path


def look(root, query, ripgrep, **options):
    return search_text(root, build_index(root).paths, query, ripgrep=ripgrep, **options)


def places(result):
    return [(hit.path, hit.line) for hit in result.hits]


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_a_lowercase_query_ignores_case_and_a_capital_makes_it_exact(project, ripgrep):
    assert places(look(project, "foo", ripgrep)) == [
        ("a.py", 1), ("a.py", 2), ("b.txt", 2), ("b.txt", 3), ("sub/c.py", 1), ("é.txt", 1)]
    assert places(look(project, "Foo", ripgrep)) == [("a.py", 2)]


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_the_query_is_literal_unless_a_pattern_is_asked_for(project, ripgrep):
    write_files(project, {"d.txt": "a.b\naxb\n"})
    assert places(look(project, "a.b", ripgrep)) == [("d.txt", 1)]
    assert places(look(project, "a.b", ripgrep, regex=True)) == [("d.txt", 1), ("d.txt", 2)]


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_a_whole_word_search_skips_longer_words(project, ripgrep):
    assert ("b.txt", 3) not in places(look(project, "foo", ripgrep, whole_word=True))
    assert ("b.txt", 2) in places(look(project, "foo", ripgrep, whole_word=True))


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_a_hit_carries_its_line_and_the_character_column_of_the_match(project, ripgrep):
    hit = next(hit for hit in look(project, "foo", ripgrep).hits if hit.path == "é.txt")
    assert hit == Hit("é.txt", 1, 2, "é foo")


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_the_search_stops_at_the_limit_and_says_so(project, ripgrep):
    result = look(project, "foo", ripgrep, limit=2)
    assert len(result.hits) == 2 and result.truncated
    assert not look(project, "foo", ripgrep).truncated


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_a_pattern_that_does_not_parse_is_an_error_not_a_crash(project, ripgrep):
    result = look(project, "foo(", ripgrep, regex=True)
    assert result.hits == [] and result.error


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_binary_files_and_an_empty_query_give_nothing(project, ripgrep):
    (project / "blob.bin").write_bytes(b"foo\0foo")
    assert "blob.bin" not in {hit.path for hit in look(project, "foo", ripgrep).hits}
    assert look(project, "", ripgrep).hits == []


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_files_that_git_ignores_are_not_searched(tmp_path, ripgrep):
    repo = make_repo(tmp_path / "repo", {".gitignore": "build/\n", "a.py": "foo\n"})
    write_files(repo, {"build/out.txt": "foo\n"})
    assert places(look(repo, "foo", ripgrep)) == [("a.py", 1)]


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_very_long_lines_are_cut_in_the_hit(project, ripgrep):
    write_files(project, {"long.txt": "foo " + "x" * 5000 + "\n"})
    hit = next(hit for hit in look(project, "foo", ripgrep).hits if hit.path == "long.txt")
    assert len(hit.text) <= 500 and hit.text.startswith("foo ")
