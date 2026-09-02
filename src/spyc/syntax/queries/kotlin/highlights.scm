; spyc is a terminal viewer for browsing code bases.
; Copyright © 2026 Adam Waldenberg, Adeptum AB, Org.nr 559494-1824.
;
; This program is free software: you can redistribute it and/or modify it
; under the terms of the GNU General Public License as published by the Free
; Software Foundation, either version 3 of the License, or (at your option)
; any later version.
;
; This program is distributed in the hope that it will be useful, but
; WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
; or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
; more details.
;
; You should have received a copy of the GNU General Public License along
; with this program. If not, see <https://www.gnu.org/licenses/>.
;
; Website: https://www.adeptum.se
; Contact: info@adeptum.se


[
  "package" "import" "class" "interface" "object" "fun" "val" "var" "typealias"
  "if" "else" "when" "for" "while" "do" "return" "try" "catch" "finally" "throw"
  "in" "is" "as" "as?" "!in" "!is" "this" "super" "constructor" "init"
  "public" "private" "protected" "internal" "abstract" "open" "final" "override"
  "data" "sealed" "enum" "companion" "const" "lateinit" "suspend" "inline"
  "operator" "infix" "vararg" "by" "where"
] @keyword

[(line_comment) (block_comment)] @comment
[(string_literal) (multiline_string_literal) (character_literal)] @string
(escape_sequence) @string.special
[(number_literal) (float_literal)] @number
(annotation) @attribute
(function_declaration name: (identifier) @function)
(call_expression (identifier) @function.call)
(class_declaration name: (identifier) @type)
(user_type (identifier) @type)
