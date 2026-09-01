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


from pygments.lexers import get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from spyc.syntax.spans import Span

TOKEN_CAPTURES = (
    (Token.Comment.Preproc, "keyword.directive"),
    (Token.Comment, "comment"),
    (Token.Keyword.Type, "type"),
    (Token.Keyword.Constant, "constant"),
    (Token.Keyword, "keyword"),
    (Token.Operator.Word, "keyword"),
    (Token.Operator, "operator"),
    (Token.Punctuation, "punctuation"),
    (Token.Name.Function, "function"),
    (Token.Name.Builtin, "function.builtin"),
    (Token.Name.Class, "type"),
    (Token.Name.Namespace, "type"),
    (Token.Name.Decorator, "attribute"),
    (Token.Name.Attribute, "attribute"),
    (Token.Name.Tag, "tag"),
    (Token.Name.Constant, "constant"),
    (Token.String.Escape, "string.special"),
    (Token.String.Doc, "string.documentation"),
    (Token.String, "string"),
    (Token.Number, "number"),
    (Token.Generic.Heading, "heading"),
    (Token.Generic.Subheading, "heading"),
    (Token.Generic.Strong, "bold"),
    (Token.Generic.Emph, "italic"),
)


def capture_for(token_type) -> str | None:
    return next((capture for candidate, capture in TOKEN_CAPTURES if token_type in candidate), None)


# The whole text is lexed up front, in the constructor, because the code view
# builds highlighters in a worker thread and only reads spans on the UI thread.
class PygmentsHighlighter:
    def __init__(self, text: str, lexer_name: str) -> None:
        self._lines = _lex(text, lexer_name)

    def spans(self, first: int, stop: int) -> list[list[Span]]:
        return [self._lines[number] if number < len(self._lines) else [] for number in range(first, stop)]


# stripnl and ensurenl are off so line numbers and columns stay those of the
# original text.
def _lex(text: str, lexer_name: str) -> list[list[Span]]:
    try:
        lexer = get_lexer_by_name(lexer_name, stripnl=False, ensurenl=False)
    except ClassNotFound:
        return [[] for _ in text.split("\n")]
    lines: list[list[Span]] = [[]]
    column = 0
    for token_type, value in lexer.get_tokens(text):
        capture = capture_for(token_type)
        for index, piece in enumerate(value.split("\n")):
            if index:
                lines.append([])
                column = 0
            if capture and piece.strip():
                _append(lines[-1], Span(column, column + len(piece), capture))
            column += len(piece)
    return lines


# Lexers emit a string's quotes and body as separate tokens; joining touching
# spans of one capture keeps each line's span list short.
def _append(line: list[Span], span: Span) -> None:
    if line and line[-1].end == span.start and line[-1].capture == span.capture:
        line[-1] = Span(line[-1].start, span.end, span.capture)
    else:
        line.append(span)
