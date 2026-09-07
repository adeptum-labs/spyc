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


from repos import make_repo, write_files
from spyc.app import SpycApp
from spyc.location import Location
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from spyc.widgets.overview_pane import OverviewPane
from spyc.widgets.status_bar import StatusBar

SIZE = (140, 40)


def make_app(root, tmp_path, start=None, **arguments):
    return SpycApp(root, start, StateStore(tmp_path / "state.json"), **arguments)


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def top_level(app):
    return [str(node.label) for node in app.query_one(FileTree).root.children]


async def test_it_starts_on_the_overview_with_the_project_in_the_tree(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert top_level(app) == ["src", "pom.xml", "README.md"]
        assert app.query_one(OverviewPane).display and not app.query_one(CodeView).display
        assert app.overview.build_systems == ("Maven",)


async def test_opening_a_file_shows_it_and_its_position(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        code = app.query_one(CodeView)
        assert code.display and not app.query_one(OverviewPane).display
        assert code.document.path == project / "src" / "app.py"
        assert app.query_one(StatusBar).text == "src/app.py · Python · 1:1 of 2"
        assert app.query_one(FileTree).cursor_node.data.path == "src/app.py"
        assert app.store.recent_files(project) == ["src/app.py"]


async def test_a_start_location_opens_the_file_at_its_line(project, tmp_path):
    app = make_app(project, tmp_path, Location("src/app.py", 2))
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.query_one(CodeView).cursor_row == 1


async def test_a_start_directory_is_revealed_in_the_tree(project, tmp_path):
    app = make_app(project, tmp_path, Location("src"))
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.query_one(FileTree).cursor_node.data.path == "src"


async def test_enter_on_a_file_in_the_tree_opens_it(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("down", "down", "enter")
        await pilot.pause()
        assert app.query_one(CodeView).document.path.name == "README.md"


async def test_f_finds_a_file_and_a_line_suffix_jumps_to_the_line(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("a", "p", "p", "colon", "2", "enter")
        await pilot.pause()
        await pilot.pause()
        code = app.query_one(CodeView)
        assert code.display_path == "src/app.py" and code.cursor_row == 1


async def test_slash_searches_in_the_file(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press(*"return", "enter")
        await pilot.pause()
        code = app.query_one(CodeView)
        assert code.match_status == "1/1" and code.cursor_row == 1
        assert app.query_one(StatusBar).text.endswith(" · 1/1")


async def test_colon_goes_to_a_line(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        await pilot.press("2", "enter")
        await pilot.pause()
        assert app.query_one(CodeView).cursor_row == 1


async def test_brackets_walk_back_and_forward_through_opened_files(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("left_square_bracket")
        await pilot.pause()
        assert app.query_one(CodeView).display_path == "src/app.py"
        await pilot.press("right_square_bracket")
        await pilot.pause()
        assert app.query_one(CodeView).display_path == "README.md"


async def test_e_opens_the_editor_at_the_cursor_line(project, tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(SpycApp, "_run_editor", lambda self, command: commands.append(command))
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.delenv("VISUAL", raising=False)
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py", 2)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
    assert commands == [["vim", "+2", str(project / "src" / "app.py")]]


async def test_p_copies_the_location(project, tmp_path, monkeypatch):
    copied = []
    monkeypatch.setattr(SpycApp, "copy_to_clipboard", lambda self, text: copied.append(text))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py", 2)
        await pilot.pause()
        await pilot.press("p")
    assert copied == ["src/app.py:2"]


async def test_i_returns_to_the_overview(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("i")
        assert app.query_one(OverviewPane).display and not app.query_one(CodeView).display


async def test_backslash_hides_the_sidebar_and_remembers_it(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("backslash")
        assert not app.query_one(FileTree).display
        assert app.store.get("sidebar") is False
    assert not make_app(project, tmp_path).store.get("sidebar", True)


async def test_tab_switches_between_the_tree_and_the_code(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        assert app.query_one(CodeView).has_focus
        await pilot.press("tab")
        assert app.query_one(FileTree).has_focus
        await pilot.press("tab")
        assert app.query_one(CodeView).has_focus


async def test_dot_shows_and_hides_ignored_files(tmp_path):
    repo = make_repo(tmp_path / "repo", {"a.py": "x = 1\n", ".gitignore": "build/\n"})
    write_files(repo, {"build/out.o": ""})
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert "build" not in top_level(app)
        await pilot.press("full_stop")
        await ready(pilot)
        assert "build" in top_level(app)


async def test_a_huge_tree_is_capped_and_the_app_stays_usable(tmp_path):
    write_files(tmp_path / "many", {f"f{number}.txt": "x" for number in range(5)})
    app = make_app(tmp_path / "many", tmp_path, max_files=3)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.overview.truncated and len(top_level(app)) == 3
        app.open_file("f0.txt")
        await pilot.pause()
        assert app.query_one(CodeView).display


async def test_a_file_that_cannot_be_opened_is_reported_not_fatal(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("nope.py")
        await pilot.pause()
        assert app.query_one(CodeView).document is None and app.query_one(OverviewPane).display
