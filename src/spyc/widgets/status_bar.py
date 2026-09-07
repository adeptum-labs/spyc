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


from rich.text import Text
from textual.widgets import Static

from spyc.status import status_line


class StatusBar(Static):
    DEFAULT_CSS = "StatusBar { height: 1; background: $panel; padding: 0 1; }"

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.text = ""

    def show(self, path: str | None, language: str | None, row: int, column: int, total: int, extra: str = "") -> None:
        self.text = status_line(path, language, row, column, total, extra)
        self.update(Text(self.text))
