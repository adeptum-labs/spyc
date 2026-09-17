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


import time
from pathlib import Path

from rich.text import Text
from textual.app import App
from textual.widgets import OptionList

from spyc.document import Document
from spyc.file_picker import FilePickerSource
from spyc.fuzzy import PathMatcher
from spyc.picking import Choice, Item
from spyc.screens.picker import Picker
from spyc.widgets.code_view import CodeView
from waiting import until


class FakeSource:
    placeholder = "Find"

    def __init__(self, names=("alpha", "beta", "alps"), line=None, column=0):
        self.names, self.line, self.column, self.previewed, self.calls = names, line, column, [], []

    def search(self, query):
        self.calls.append(query)
        return [Item(name, Text(name), self.line, self.column) for name in self.names if query in name]

    def preview(self, item):
        self.previewed.append(item.key)


class PickerApp(App):
    def __init__(self, source):
        super().__init__()
        self.source, self.result, self.moves, self.picker_query = source, "unset", [], ""

    async def on_mount(self):
        await self.push_screen(Picker(self.source, self.picker_query), self.done)

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


async def test_only_the_item_you_stop_on_is_previewed(monkeypatch):
    monkeypatch.setattr("spyc.screens.picker.PREVIEW_DELAY", 0.5)
    source = FakeSource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.press("down", "down")
        await pilot.pause(1.0)
    assert source.previewed[-1] == "alps" and "beta" not in source.previewed


async def test_a_file_preview_shows_the_file_and_keeps_its_cursor_to_itself(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n" * 50)
    app = PickerApp(FilePickerSource(tmp_path, PathMatcher(["src/app.py"]), lambda: []))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("a", "p", "p", "colon", "4", "0")
        view = pilot.app.screen.query_one(CodeView)
        await until(pilot, lambda: view.document is not None and view.document.path.name == "app.py" and view.cursor_row == 39)
    assert app.moves == []


async def test_the_preview_is_hidden_on_a_narrow_terminal():
    async with PickerApp(FakeSource()).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert pilot.app.screen.has_class("-narrow")
    async with PickerApp(FakeSource()).run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert not pilot.app.screen.has_class("-narrow")


class SlowSource(FakeSource):
    threaded = True

    def __init__(self, debounce=0.0):
        super().__init__(())
        self.debounce, self.calls = debounce, []

    def search(self, query):
        self.calls.append(query)
        time.sleep(0.6 if query == "a" else 0)
        return [Item(query or "(empty)", Text(f"result for {query!r}"))]


class ModalSource(FakeSource):
    def __init__(self):
        super().__init__(("one",))
        self.regex, self.searches = False, []

    def toggle_regex(self):
        self.regex = not self.regex

    def mode_text(self):
        return "regex" if self.regex else "literal"

    def summary(self):
        return f"{len(self.searches)} searches"

    def search(self, query):
        self.searches.append(query)
        return [Item("one", Text("one"))]


async def test_a_slow_search_never_replaces_the_results_of_a_newer_one():
    async with PickerApp(SlowSource()).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a", "b")
        await until(pilot, lambda: rows(pilot) == ["result for 'ab'"])
        await pilot.pause(1.0)
        assert rows(pilot) == ["result for 'ab'"]


async def test_typing_fast_searches_once_when_the_source_wants_a_pause():
    source = SlowSource(debounce=1.0)
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("x", "y", "z")
        await until(pilot, lambda: rows(pilot) == ["result for 'xyz'"])
    assert source.calls == ["", "xyz"]


async def test_a_source_can_switch_modes_and_says_what_it_found():
    source = ModalSource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        status = pilot.app.screen.query_one("#picker-status")
        assert status.render().plain == "literal  1 searches"
        await pilot.press("alt+r")
        await pilot.pause()
        assert source.regex and status.render().plain == "regex  2 searches"


async def test_a_picker_can_start_with_a_query_already_typed():
    app = PickerApp(FakeSource())
    app.picker_query = "al"
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert rows(pilot) == ["alpha", "alps"]
        assert pilot.app.screen.query_one("Input").value == "al"


async def test_the_column_of_an_item_travels_with_the_choice():
    app = PickerApp(FakeSource(line=7, column=4))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == Choice("alpha", 7, 4)


async def test_a_query_typed_in_advance_is_searched_once():
    source = FakeSource()
    app = PickerApp(source)
    app.picker_query = "al"
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
    assert source.calls == ["al"]


async def test_typing_a_query_back_to_the_one_shown_does_not_search_again():
    source = FakeSource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.press("a", "backspace")
        await pilot.pause()
    assert source.calls == ["", "a", ""]


class VanishingSource(FakeSource):
    def preview(self, item):
        return Document(Path("alpha"), ("alpha text",), None, 0.0) if item.key == "alpha" else None


async def test_the_preview_of_a_file_that_is_gone_replaces_the_one_before_it(monkeypatch):
    monkeypatch.setattr("spyc.screens.picker.PREVIEW_DELAY", 0.05)
    async with PickerApp(VanishingSource()).run_test(size=(120, 40)) as pilot:
        view = pilot.app.screen.query_one(CodeView)
        await until(pilot, lambda: view.document is not None and view.document.lines == ("alpha text",))
        await pilot.press("down")
        await until(pilot, lambda: view.document.notice is not None)


class BusySource(SlowSource):
    def __init__(self, debounce=0.0):
        super().__init__(debounce)
        self.active = self.most_active = 0
        self.cancelled = 0

    def cancel(self):
        self.cancelled += 1

    def search(self, query):
        self.active += 1
        self.most_active = max(self.most_active, self.active)
        try:
            return super().search(query)
        finally:
            self.active -= 1


async def test_a_new_search_cancels_the_running_one_and_never_overlaps_it():
    source = BusySource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a", "b")
        await until(pilot, lambda: rows(pilot) == ["result for 'ab'"])
        assert source.most_active == 1 and source.cancelled >= 2


async def test_closing_the_picker_cancels_the_running_search():
    source = BusySource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        before = source.cancelled
        await pilot.press("escape")
        await pilot.pause()
        assert source.cancelled > before


async def test_enter_while_the_answer_to_what_was_typed_is_pending_chooses_nothing():
    app = PickerApp(SlowSource(debounce=0.4))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("x", "enter")
        await pilot.pause(0.1)
        assert app.result == "unset"
        await until(pilot, lambda: rows(pilot) == ["result for 'x'"])
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == Choice("x", None)


class FailingSource(SlowSource):
    def search(self, query):
        if query == "x":
            raise RuntimeError("boom")
        return super().search(query)


async def test_a_search_that_fails_leaves_the_picker_usable():
    app = PickerApp(FailingSource())
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("x")
        await until(pilot, lambda: rows(pilot) == [])
        await pilot.press("backspace", "y")
        await until(pilot, lambda: rows(pilot) == ["result for 'y'"])
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == Choice("y", None)


class KeyedSource(ModalSource):
    def __init__(self):
        super().__init__()
        self.word = False

    def toggle_word(self):
        self.word = not self.word


async def test_the_function_keys_switch_the_modes_where_the_terminal_swallows_alt():
    source = KeyedSource()
    async with PickerApp(source).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f2", "f3")
        await pilot.pause()
        assert source.regex and source.word
