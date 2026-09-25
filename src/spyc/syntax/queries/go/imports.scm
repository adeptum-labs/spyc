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


(import_spec) @spec
(selector_expression operand: (identifier) @operand field: (field_identifier) @field)
(source_file (function_declaration name: (identifier) @define))
(source_file (type_declaration (type_spec name: (type_identifier) @define)))
(source_file (type_declaration (type_alias name: (type_identifier) @define)))
(source_file (const_declaration (const_spec name: (identifier) @define)))
(source_file (var_declaration (var_spec name: (identifier) @define)))
(source_file (var_declaration (var_spec_list (var_spec name: (identifier) @define))))
