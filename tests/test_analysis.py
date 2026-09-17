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


import spyc.analysis
from spyc.analysis import analyse
from spyc.languages import LANGUAGES_BY_ID

JAVA = "package a.b;\nimport c.D;\npublic class A { void m() {} }\n"


class CountingParser:
    def __init__(self, parser, parses):
        self._parser, self._parses = parser, parses

    def parse(self, data):
        self._parses.append(len(data))
        return self._parser.parse(data)


def test_one_parse_gives_the_definitions_and_the_facts(monkeypatch):
    parses, real = [], spyc.analysis.Parser
    monkeypatch.setattr("spyc.analysis.Parser", lambda language: CountingParser(real(language), parses))
    result = analyse(JAVA, LANGUAGES_BY_ID["java"])
    assert [symbol.name for symbol in result.symbols] == ["A", "m"]
    assert result.facts.unit == "a.b" and [imported.path for imported in result.facts.imports] == ["c.D"]
    assert len(parses) == 1


def test_a_language_with_definitions_only_has_no_facts_and_markdown_gives_headings():
    assert analyse("def f(): pass\n", LANGUAGES_BY_ID["python"]).facts is None
    assert [symbol.name for symbol in analyse("# T\n", LANGUAGES_BY_ID["markdown"]).symbols] == ["T"]


def test_no_language_and_a_language_without_queries_give_nothing():
    assert analyse("x", None).symbols == [] and analyse("a = 1\n", LANGUAGES_BY_ID["yaml"]).facts is None
