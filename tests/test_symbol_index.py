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


import json
import os
import time

import pytest

import spyc.symbol_index
from repos import write_files
from spyc.languages import detect_language
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


def test_files_that_did_not_change_are_not_read_again_from_the_cache(project, tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    SymbolIndex(project, cache).update(PATHS)
    parsed = []
    real = spyc.symbol_index.analyse
    monkeypatch.setattr(spyc.symbol_index, "analyse", lambda text, language: parsed.append(language.id) or real(text, language))
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
    assert index.all() == ()


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


def test_creating_an_index_reads_nothing_and_the_cache_is_read_by_the_update(project, tmp_path):
    cache = tmp_path / "cache.json"
    SymbolIndex(project, cache).update(PATHS)
    later = SymbolIndex(project, cache)
    assert later.all() == ()
    later.update(PATHS)
    assert len(later.all()) == 4


def test_a_cache_that_nothing_changed_is_not_written_again(project, tmp_path):
    cache = tmp_path / "cache.json"
    SymbolIndex(project, cache).update(PATHS)
    os.utime(cache, ns=(1, 1))
    SymbolIndex(project, cache).update(PATHS)
    assert cache.stat().st_mtime_ns == 1
    (project / "a.py").write_text("def other():\n    pass\n")
    SymbolIndex(project, cache).update(PATHS)
    assert cache.stat().st_mtime_ns != 1


def test_two_saves_never_share_a_temporary_file(project, tmp_path, monkeypatch):
    sources = []
    real = os.replace
    monkeypatch.setattr(spyc.symbol_index.os, "replace", lambda source, target: sources.append(source) or real(source, target))
    SymbolIndex(project, tmp_path / "cache.json").update(PATHS)
    SymbolIndex(project, tmp_path / "cache.json").update(("a.py",))
    assert len(sources) == 2 and sources[0] != sources[1]
    assert sorted(path.name for path in tmp_path.glob("cache*")) == ["cache.json"]


def test_a_cache_from_another_version_of_the_grammars_is_not_trusted(project, tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(spyc.symbol_index, "_signature", lambda: "spyc 1, tree-sitter-python 1")
    SymbolIndex(project, cache).update(PATHS)
    parsed = []
    real = spyc.symbol_index.analyse
    monkeypatch.setattr(spyc.symbol_index, "analyse", lambda text, language: parsed.append(language.id) or real(text, language))
    SymbolIndex(project, cache).update(PATHS)
    assert parsed == []
    monkeypatch.setattr(spyc.symbol_index, "_signature", lambda: "spyc 1, tree-sitter-python 2")
    SymbolIndex(project, cache).update(PATHS)
    assert sorted(parsed) == ["java", "markdown", "python"]


def test_the_signature_names_spyc_and_the_grammars_in_use():
    signature = spyc.symbol_index._signature()
    assert "spyc=" in signature and "tree-sitter-python=" in signature


def test_lookups_follow_the_files_as_they_are_indexed(project):
    index = SymbolIndex(project)
    index.update(("a.py",))
    assert names(index.lookup("foo")) == [("a.py", "foo", 1)]
    write_files(project, {"c.py": "def foo(): pass\n"})
    index.update(("a.py", "c.py"))
    assert names(index.lookup("foo")) == [("a.py", "foo", 1), ("c.py", "foo", 1)]


from spyc.deps.facts import ClassDef, FileFacts, Import

JAVA_FILES = {"a/A.java": "package a;\nimport b.B;\nclass A {}\n", "b/B.java": "package b;\nclass B {}\n", "README.md": "# T\n"}
JAVA_PATHS = tuple(sorted(JAVA_FILES))


def test_the_facts_of_java_files_are_kept_and_files_without_import_queries_have_none(tmp_path):
    write_files(tmp_path, JAVA_FILES)
    index = SymbolIndex(tmp_path)
    index.update(JAVA_PATHS)
    assert index.facts() == {
        "a/A.java": FileFacts("a", (ClassDef("A", 3),), (Import("b.B"),), frozenset({"B", "A"}), "java"),
        "b/B.java": FileFacts("b", (ClassDef("B", 2),), (), frozenset({"B"}), "java")}


def test_facts_come_back_from_the_cache_without_parsing_and_files_that_are_gone_lose_theirs(tmp_path, monkeypatch):
    write_files(tmp_path / "p", JAVA_FILES)
    cache = tmp_path / "cache.json"
    first = SymbolIndex(tmp_path / "p", cache)
    first.update(JAVA_PATHS)
    parsed = []
    real = spyc.symbol_index.analyse
    monkeypatch.setattr(spyc.symbol_index, "analyse", lambda text, language: parsed.append(language.id) or real(text, language))
    later = SymbolIndex(tmp_path / "p", cache)
    later.update(JAVA_PATHS)
    assert parsed == [] and later.facts() == first.facts()
    later.update(("b/B.java",))
    assert set(later.facts()) == {"b/B.java"}


def test_facts_is_a_copy_that_the_caller_may_keep(tmp_path):
    write_files(tmp_path, JAVA_FILES)
    index = SymbolIndex(tmp_path)
    index.update(JAVA_PATHS)
    taken = index.facts()
    index.update(())
    assert set(taken) == {"a/A.java", "b/B.java"} and index.facts() == {}


def test_a_cache_whose_facts_have_the_wrong_kinds_of_values_is_ignored_and_the_files_are_read_again(tmp_path):
    write_files(tmp_path / "p", {"a/A.java": "package a;\nimport b.B;\nclass A {}\n"})
    cache = tmp_path / "cache.json"
    first = SymbolIndex(tmp_path / "p", cache)
    first.update(("a/A.java",))
    data = json.loads(cache.read_text())
    data["files"]["a/A.java"]["facts"]["imports"] = [[123, False, False]]
    cache.write_text(json.dumps(data))
    later = SymbolIndex(tmp_path / "p", cache)
    later.update(("a/A.java",))
    assert later.facts()["a/A.java"].imports == (Import("b.B"),)


def test_a_go_module_file_is_indexed_for_its_module_path_and_is_not_taken_for_modula_2(tmp_path):
    write_files(tmp_path / "project", {"go.mod": "module example.com/x\n", "sub/go.mod": "module example.com/x/sub\n",
                                       "main.go": "package main\n"})
    index = SymbolIndex(tmp_path / "project")
    index.update(("go.mod", "main.go", "sub/go.mod"))
    assert [index.facts()[path].imports[0].path for path in ("go.mod", "sub/go.mod")] == ["example.com/x", "example.com/x/sub"]
    assert detect_language("go.mod").id == "gomod"
