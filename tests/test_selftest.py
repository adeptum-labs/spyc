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


import spyc.__main__ as entry
import spyc.selftest as selftest


def test_a_complete_installation_has_nothing_to_report():
    assert selftest.problems() == []


def test_a_grammar_that_cannot_be_loaded_is_named(monkeypatch):
    real = selftest.load_grammar
    monkeypatch.setattr(selftest, "load_grammar", lambda language: None if language.id == "python" else real(language))
    assert selftest.problems() == ["No tree-sitter grammar for Python"]


def test_a_tags_query_that_cannot_be_loaded_is_named(monkeypatch):
    monkeypatch.setattr(selftest, "load_tags", lambda language: None)
    assert "No definition queries for Python" in selftest.problems()


def test_a_definition_query_that_does_not_compile_is_named(monkeypatch):
    real = selftest.load_tags
    monkeypatch.setattr(selftest, "load_tags",
                        lambda language: (real(language)[0], "(no_such_node_type) @name") if language.id == "python" else real(language))
    (problem,) = selftest.problems()
    assert problem.startswith("Definition queries for Python do not compile: ")


def test_a_language_that_fails_to_highlight_is_named(monkeypatch):
    def broken(language, text):
        raise RuntimeError("boom")

    monkeypatch.setattr(selftest, "make_highlighter", broken)
    found = selftest.problems()
    assert "Highlighting Python failed: boom" in found and "Highlighting Dockerfile failed: boom" in found


def test_a_broken_xml_reader_is_named(monkeypatch):
    def broken(text, root_tag):
        raise RuntimeError("no defusedxml")

    monkeypatch.setattr(selftest, "parse_xml", broken)
    assert selftest.problems() == ["Reading XML reports failed: no defusedxml"]


def test_the_self_test_flag_reports_success(capsys):
    assert entry.main(["--self-test"]) == 0
    assert "self-test passed" in capsys.readouterr().out


def test_the_self_test_flag_reports_every_problem_and_fails(monkeypatch, capsys):
    monkeypatch.setattr(entry, "problems", lambda: ["No tree-sitter grammar for Python", "Highlighting Go failed: boom"])
    assert entry.main(["--self-test"]) == 1
    assert capsys.readouterr().err.splitlines() == ["spyc: No tree-sitter grammar for Python", "spyc: Highlighting Go failed: boom"]


def test_an_import_query_that_does_not_compile_is_named(monkeypatch):
    real = selftest.load_imports
    monkeypatch.setattr(selftest, "load_imports",
                        lambda language: (real(language)[0], "(no_such_node_type) @name") if language.id == "java" else real(language))
    (problem,) = selftest.problems()
    assert problem.startswith("Import queries for Java do not compile: ")


def test_import_queries_that_cannot_be_loaded_are_named(monkeypatch):
    monkeypatch.setattr(selftest, "load_imports", lambda language: None)
    assert {"No import queries for Java", "No import queries for Kotlin"} <= set(selftest.problems())
