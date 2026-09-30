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


from spyc.core.languages import LANGUAGES, Language
from spyc.coverage.safe_xml import parse_xml
from spyc.syntax.factory import make_highlighter
from spyc.syntax.grammars import load_grammar, load_imports, load_tags
from spyc.syntax.tree_sitter_highlighter import compile_query


# What a packaged executable can lose without saying so: a grammar wheel, a
# query file or a lexer that PyInstaller did not see. Colors would then silently
# fall back, so the release checks for it.
def problems() -> list[str]:
    found = []
    for language in LANGUAGES:
        if language.grammar and load_grammar(language) is None:
            found.append(f"No tree-sitter grammar for {language.name}")
        found += _query_problem(language, "definition", language.tags, load_tags)
        found += _query_problem(language, "import", language.imports, load_imports)
        found += _highlighting_problem(language)
    return found + _xml_problem()


# Loading the queries only reads their text; they are compiled when the outline or the graph is asked for.
def _query_problem(language: Language, kind: str, references: tuple, load) -> list[str]:
    if not references:
        return []
    loaded = load(language)
    if loaded is None:
        return [f"No {kind} queries for {language.name}"]
    try:
        compile_query(*loaded)
    except Exception as error:
        return [f"{kind.capitalize()} queries for {language.name} do not compile: {error}"]
    return []


def _highlighting_problem(language: Language) -> list[str]:
    try:
        make_highlighter(language, "x\n")
    except Exception as error:
        return [f"Highlighting {language.name} failed: {error}"]
    return []


def _xml_problem() -> list[str]:
    try:
        parse_xml("<coverage/>", "coverage")
    except Exception as error:
        return [f"Reading XML reports failed: {error}"]
    return []
