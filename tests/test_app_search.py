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

from repos import write_files
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


SYMBOL_FILES = {
    "src/app.py": "def helper():\n    pass\n\n\ndef main():\n    helper()\n",
    "src/util.py": "def helper():\n    return 1\n",
    "src/only.py": "def unique_fn():\n    pass\n",
    "src/user.py": "unique_fn()\n",
    "src/lost.py": "mystery()\n",
    "notes.txt": "plain\n",
}


async def indexed(pilot):
    await ready(pilot)
    await until(pilot, lambda: pilot.app._symbols.total and pilot.app._symbols.done == pilot.app._symbols.total)


def picker_rows(app):
    options = app.screen.query_one(OptionList)
    return [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]


async def test_o_lists_the_definitions_of_the_open_file_and_enter_jumps_to_one(tmp_path):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("o")
        await until(pilot, lambda: isinstance(app.screen, Picker) and app.screen.query_one(OptionList).option_count == 2)
        await pilot.press(*"main", "enter")
        await until(pilot, lambda: not isinstance(app.screen, Picker))
        await until(pilot, lambda: app.query_one(CodeView).cursor_row == 4)


async def test_o_explains_itself_without_a_file_or_an_outline(tmp_path, monkeypatch):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("o")
        app.open_file("notes.txt")
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        assert notes == ["Open a file to see its outline", "No outline for this file"]


async def test_t_finds_a_definition_anywhere_in_the_project(tmp_path):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await indexed(pilot)
        await pilot.press("t")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press(*"unique")
        await until(pilot, lambda: len(picker_rows(app)) == 1)
        assert picker_rows(app)[0].endswith("src/only.py:1")
        await pilot.press("enter")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/only.py")


async def test_d_jumps_to_the_only_definition_of_the_name_under_the_cursor(tmp_path):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await indexed(pilot)
        app.open_file("src/user.py")
        await pilot.pause()
        await pilot.press("d")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/only.py")
        assert app.query_one(CodeView).cursor_row == 0
        await pilot.press("left_square_bracket")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/user.py")


async def test_d_offers_the_candidates_nearest_first_when_there_are_several(tmp_path):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await indexed(pilot)
        app.open_file("src/app.py", 6)
        await pilot.pause()
        app.query_one(CodeView).goto(6, 4)
        await pilot.press("d")
        await until(pilot, lambda: isinstance(app.screen, Picker) and len(picker_rows(app)) == 2)
        assert [row.split()[-1] for row in picker_rows(app)] == ["src/app.py:1", "src/util.py:1"]


async def test_d_falls_back_to_the_places_the_name_is_used_when_it_is_not_defined(tmp_path, monkeypatch):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await indexed(pilot)
        app.open_file("src/lost.py")
        await pilot.pause()
        await pilot.press("d")
        await until(pilot, lambda: isinstance(app.screen, Picker) and app.screen.query_one("Input").value == "mystery")
        await until(pilot, lambda: len(picker_rows(app)) == 1)
        assert "whole word" in app.screen.query_one("#picker-status").render().plain
        assert notes == ["No definition of mystery found; showing where it is used"]


async def test_d_on_the_definition_itself_shows_the_uses_instead(tmp_path):
    write_files(tmp_path / "proj", SYMBOL_FILES)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await indexed(pilot)
        app.open_file("src/only.py")
        await pilot.pause()
        app.query_one(CodeView).goto(1, 4)
        await pilot.press("d")
        await until(pilot, lambda: isinstance(app.screen, Picker) and app.screen.query_one("Input").value == "unique_fn")


async def test_d_needs_the_cursor_on_a_name(tmp_path, monkeypatch):
    write_files(tmp_path / "proj", {"a.py": "x = (\n"})
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("a.py")
        await pilot.pause()
        app.query_one(CodeView).goto(1, 4)
        await pilot.press("d")
        await pilot.pause()
        assert notes == ["Put the cursor on a name first"]
