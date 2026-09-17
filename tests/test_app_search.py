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


from textual.widgets import OptionList

from spyc.app import SpycApp
from spyc.screens.picker import Picker
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from waiting import until

SIZE = (140, 40)


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_s_searches_the_text_of_the_project_and_enter_opens_the_hit(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("s")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press(*"return")
        await until(pilot, lambda: app.screen.query_one(OptionList).option_count == 1)
        assert app.screen.query_one("#picker-status").render().plain == "literal  1 hits"
        await pilot.press("enter")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/app.py")
        await until(pilot, lambda: app.query_one(CodeView).cursor_row == 1)


async def test_s_before_the_files_are_known_says_so(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        app._paths = None
        await pilot.press("s")
        await pilot.pause()
        assert notes == ["Still reading the project files"]
