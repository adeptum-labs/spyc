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


TAB = 9
NEWLINE = 10
DELETE = 0x7F
C1_CONTROLS = range(0x80, 0xA0)
SURROGATES = range(0xD800, 0xE000)

# Text from files goes to the terminal as it is, so a control character in it is
# a command to the terminal (clear the screen, set the clipboard). Each one is
# shown as its symbol from the Control Pictures block instead, one for one, so
# columns and offsets do not shift. A file name that is not valid UTF-8 reaches
# Python as lone surrogates, which cannot be written to a terminal at all.
_CONTROLS = {code: chr(0x2400 + code) for code in range(32) if code != TAB} | {DELETE: "␡"}
_CONTROLS |= {code: "�" for code in (*C1_CONTROLS, *SURROGATES)}
_KEEPING_NEWLINES = {code: symbol for code, symbol in _CONTROLS.items() if code != NEWLINE}


def printable(text: str, *, keep_newlines: bool = False) -> str:
    return text.translate(_KEEPING_NEWLINES if keep_newlines else _CONTROLS)
