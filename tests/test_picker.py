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
from textual.app import App
from textual.widgets import OptionList

from spyc.file_picker import FilePickerSource
from spyc.fuzzy import PathMatcher
from spyc.picking import Choice, Item
from spyc.screens.picker import Picker
from spyc.widgets.code_view import CodeView


class FakeSource:
    placeholder = "Find"

    def __init__(self, names=("alpha", "beta", "alps"), line=None):
        self.names, self.line, self.previewed = names, line, []

    def search(self, query):
        return [Item(name, Text(name), self.line) for name in self.names if query in name]

    def preview(self, item):
        self.previewed.append(item.key)


class PickerApp(App):
    def __init__(self, source):
        super().__init__()
        self.source, self.result, self.moves = source, "unset", []

    async def on_mount(self):
        await self.push_screen(Picker(self.source), self.done)

    def done(self, result):
        self.result = result

    def on_code_view_cursor_moved(self, message):
        self.moves.append((message.row, message.column))


def rows(pilot):
    options = pilot.app.screen.query_one(OptionList)
    return [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]


async def test_typing_filters_the_list():
    async with PickerApp(FakeSource()).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert rows(pilot) == ["alpha", "beta", "alps"]
        await pilot.press("a", "l")
        assert rows(pilot) == ["alpha", "alps"]


async def test_enter_chooses_the_highlighted_item():
    app = PickerApp(FakeSource())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("down", "enter")
        await pilot.pause()
    assert app.result == Choice("beta", None)


async def test_the_line_of_an_item_travels_with_the_choice():
    app = PickerApp(FakeSource(line=7))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == Choice("alpha", 7)


async def test_up_stops_at_the_first_item_and_down_at_the_last():
    app = PickerApp(FakeSource())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("up", "down", "down", "down", "down", "enter")
        await pilot.pause()
    assert app.result == Choice("alps", None)


async def test_escape_cancels():
    app = PickerApp(FakeSource())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None


async def test_enter_with_nothing_to_choose_does_nothing():
    app = PickerApp(FakeSource())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("z", "z", "enter")
        await pilot.pause()
        assert app.result == "unset"
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None


async def test_only_the_item_you_stop_on_is_previewed():
    source = FakeSource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.press("down", "down")
        await pilot.pause(0.4)
    assert source.previewed[-1] == "alps" and "beta" not in source.previewed


async def test_a_file_preview_shows_the_file_and_keeps_its_cursor_to_itself(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n" * 50)
    app = PickerApp(FilePickerSource(tmp_path, PathMatcher(["src/app.py"]), lambda: []))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("a", "p", "p", "colon", "4", "0")
        await pilot.pause(0.4)
        view = pilot.app.screen.query_one(CodeView)
        assert view.document.path.name == "app.py" and view.cursor_row == 39
    assert app.moves == []


async def test_the_preview_is_hidden_on_a_narrow_terminal():
    async with PickerApp(FakeSource()).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert pilot.app.screen.has_class("-narrow")
    async with PickerApp(FakeSource()).run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert not pilot.app.screen.has_class("-narrow")
