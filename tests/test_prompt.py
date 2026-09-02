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


from textual.app import App

from spyc.screens.prompt import Prompt


class PromptApp(App):
    def __init__(self, prompt):
        super().__init__()
        self.prompt, self.result = prompt, "unset"

    async def on_mount(self):
        await self.push_screen(self.prompt, self.done)

    def done(self, value):
        self.result = value


async def test_enter_returns_the_typed_value():
    app = PromptApp(Prompt("Go to line", restrict=r"[0-9]*"))
    async with app.run_test() as pilot:
        await pilot.press("4", "x", "2", "enter")
        await pilot.pause()
    assert app.result == "42"


async def test_escape_returns_none():
    app = PromptApp(Prompt("Find", "old"))
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None
