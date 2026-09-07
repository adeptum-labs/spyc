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


from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown


class MarkdownPane(VerticalScroll, can_focus=True):
    DEFAULT_CSS = "MarkdownPane { padding: 0 2; }"

    def compose(self) -> ComposeResult:
        yield Markdown()

    async def show(self, text: str) -> None:
        await self.query_one(Markdown).update(text)
