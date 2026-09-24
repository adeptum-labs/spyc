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


from dataclasses import dataclass, replace

from tree_sitter import Parser

from spyc.deps.extract import facts_of
from spyc.deps.facts import FileFacts
from spyc.languages import Language
from spyc.symbols import Symbol, definitions_in, headings_of
from spyc.syntax.grammars import load_imports, load_tags
from spyc.syntax.tree_sitter_highlighter import compile_query


@dataclass(frozen=True)
class Analysis:
    symbols: list[Symbol]
    facts: FileFacts | None


# One parse serves the outline and the dependency graph.
def analyse(text: str, language: Language | None) -> Analysis:
    if language is None:
        return Analysis([], None)
    if language.id == "markdown":
        return Analysis(headings_of(text), None)
    tags, imports = load_tags(language), load_imports(language)
    grammar = tags or imports
    if grammar is None:
        return Analysis([], None)
    data = text.encode("utf-8")
    tree = Parser(grammar[0]).parse(data)
    facts = facts_of(tree, compile_query(*imports)) if imports else None
    return Analysis(definitions_in(data, tree, *tags) if tags else [],
                    None if facts is None else replace(facts, language=language.id))
