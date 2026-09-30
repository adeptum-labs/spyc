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
import shutil
import threading
import time

import pytest

from repos import make_repo, write_files
from spyc.core.cancellation import Cancellation
from spyc.core.file_index import build_index
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


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")
def test_a_pattern_search_matches_by_regular_expression(project):
    write_files(project, {"d.txt": "a.b\naxb\n"})
    assert places(look(project, "a.b", True, regex=True)) == [("d.txt", 1), ("d.txt", 2)]


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


def test_a_search_cancelled_before_it_starts_finds_nothing(project):
    cancellation = Cancellation()
    cancellation.cancel()
    assert look(project, "foo", False, cancellation=cancellation).hits == []


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a shell to stand in for ripgrep")
def test_cancelling_stops_a_ripgrep_that_is_still_working(project, tmp_path, monkeypatch):
    fake = tmp_path / "bin" / "rg"
    write_files(tmp_path, {"bin/rg": "#!/bin/sh\nexec sleep 30\n"})
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    cancellation = Cancellation()
    threading.Timer(0.2, cancellation.cancel).start()
    started = time.monotonic()
    assert look(project, "foo", True, cancellation=cancellation).hits == []
    assert time.monotonic() - started < 10


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_a_query_with_a_nul_character_finds_nothing_and_does_not_crash(project, ripgrep):
    result = look(project, "fo\0o", ripgrep)
    assert result.hits == [] and result.error is None


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_text_and_names_that_are_not_utf8_are_still_found(project, ripgrep):
    (project / os.fsdecode(b"caf\xe9.txt")).write_bytes(b"caf\xe9 foo\n")
    hit = next(hit for hit in look(project, "foo", ripgrep).hits if hit.path.startswith("caf"))
    assert (hit.line, hit.column, hit.text) == (1, 5, "caf� foo")
    assert (project / hit.path).is_file()


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")
def test_the_users_ripgrep_configuration_does_not_change_the_results(project, tmp_path, monkeypatch):
    write_files(tmp_path, {"rgrc": "--max-count=1\n"})
    monkeypatch.setenv("RIPGREP_CONFIG_PATH", str(tmp_path / "rgrc"))
    assert places(look(project, "foo", True))[:2] == [("a.py", 1), ("a.py", 2)]


def test_a_pattern_search_without_ripgrep_says_it_needs_ripgrep(project):
    result = look(project, "fo+", False, regex=True)
    assert result.hits == [] and result.error == "Pattern search needs ripgrep"


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")
def test_a_bad_pattern_is_reported_as_one(project):
    assert look(project, "foo(", True, regex=True).error.startswith("Bad pattern: ")


@pytest.mark.parametrize("ripgrep", BACKENDS)
def test_hits_come_back_in_path_order(project, ripgrep):
    write_files(project, {f"dir{index}/file.txt": "foo\n" for index in range(20)})
    paths = [hit.path for hit in look(project, "foo", ripgrep).hits]
    assert paths == sorted(paths)
