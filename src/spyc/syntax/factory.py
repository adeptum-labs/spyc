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


from spyc.core.languages import Language
from spyc.syntax.grammars import load_grammar
from spyc.syntax.pygments_highlighter import PygmentsHighlighter
from spyc.syntax.spans import Highlighter, PlainHighlighter
from spyc.syntax.tree_sitter_highlighter import TreeSitterHighlighter


def make_highlighter(language: Language | None, text: str) -> Highlighter:
    if language is None:
        return PlainHighlighter()
    grammar = load_grammar(language)
    if grammar is not None:
        return TreeSitterHighlighter(text, *grammar)
    if language.lexer is not None:
        return PygmentsHighlighter(text, language.lexer)
    return PlainHighlighter()
