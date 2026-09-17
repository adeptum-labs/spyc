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
import time

import pytest

import spyc.symbol_index
from repos import write_files
from spyc.symbol_index import Located, SymbolIndex, default_cache_path
from spyc.symbols import Symbol

FILES = {"a.py": "def foo():\n    pass\n", "src/B.java": "class B { void foo() {} }\n", "notes.txt": "def foo\n",
         "README.md": "# foo\n"}
PATHS = tuple(sorted(FILES))


@pytest.fixture
def project(tmp_path):
    write_files(tmp_path / "project", FILES)
    return tmp_path / "project"


def names(located):
    return sorted((item.path, item.symbol.name, item.symbol.line) for item in located)


def test_tagged_files_are_indexed_and_other_files_are_not(project):
    index = SymbolIndex(project)
    index.update(PATHS)
    assert names(index.all()) == [("README.md", "foo", 1), ("a.py", "foo", 1), ("src/B.java", "B", 1),
                                  ("src/B.java", "foo", 1)]
    assert (index.done, index.total) == (3, 3)


def test_a_name_is_looked_up_across_files_without_headings(project):
    index = SymbolIndex(project)
    index.update(PATHS)
    assert names(index.lookup("foo")) == [("a.py", "foo", 1), ("src/B.java", "foo", 1)]
    assert index.lookup("nothing") == []


def test_the_definitions_of_one_file_can_be_asked_for(project):
    index = SymbolIndex(project)
    index.update(PATHS)
    assert [symbol.name for symbol in index.in_file("src/B.java")] == ["B", "foo"]
    assert index.in_file("missing.py") == []


def test_files_that_did_not_change_are_not_read_again_from_the_cache(project, tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    SymbolIndex(project, cache).update(PATHS)
    parsed = []
    real = spyc.symbol_index.symbols_of
    monkeypatch.setattr(spyc.symbol_index, "symbols_of", lambda text, language: parsed.append(language.id) or real(text, language))
    later = SymbolIndex(project, cache)
    later.update(PATHS)
    assert parsed == [] and names(later.lookup("foo")) == [("a.py", "foo", 1), ("src/B.java", "foo", 1)]
    (project / "a.py").write_text("def bar():\n    pass\n")
    os.utime(project / "a.py", (time.time() + 5, time.time() + 5))
    later.update(PATHS)
    assert parsed == ["python"] and later.lookup("bar")[0].path == "a.py" and len(later.lookup("foo")) == 1


def test_files_that_are_gone_are_dropped(project):
    index = SymbolIndex(project)
    index.update(PATHS)
    index.update(("a.py",))
    assert {item.path for item in index.all()} == {"a.py"}


def test_binary_and_huge_files_are_skipped(project, monkeypatch):
    write_files(project, {"big.py": "def huge(): pass\n"})
    (project / "bin.py").write_bytes(b"def nul(): pass\0")
    monkeypatch.setattr(spyc.symbol_index, "MAX_SYMBOL_FILE", 10)
    index = SymbolIndex(project)
    index.update(("big.py", "bin.py"))
    assert index.all() == []


def test_the_update_can_be_stopped(project):
    index = SymbolIndex(project)
    calls = []
    index.update(PATHS, stop=lambda: calls.append(1) or len(calls) > 1)
    assert index.done < index.total


def test_a_broken_cache_file_is_ignored(project, tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text("{not json")
    index = SymbolIndex(project, cache)
    index.update(PATHS)
    assert names(index.lookup("foo"))


def test_the_cache_lives_under_xdg_cache_home_per_project(monkeypatch, tmp_path, project):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache-home"))
    first, other = default_cache_path(project), default_cache_path(tmp_path)
    assert first.parent == tmp_path / "cache-home" / "spyc" and first != other


def test_located_entries_compare_by_value():
    assert Located("a.py", Symbol("f", "function", 1, 4)) == Located("a.py", Symbol("f", "function", 1, 4))
