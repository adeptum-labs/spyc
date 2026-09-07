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


import os

from repos import write_files
from spyc.app import SpycApp
from spyc.screens.help import HelpScreen
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.markdown_pane import MarkdownPane
from spyc.widgets.status_bar import StatusBar

SIZE = (140, 40)


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def change(path, content):
    path.write_text(content)
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


async def test_a_changed_file_is_reloaded_at_the_same_place(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py", 2)
        await pilot.pause()
        change(project / "src" / "app.py", "def main():\n    return 2\n# new\n")
        await app._check_for_changes()
        await pilot.pause()
        code = app.query_one(CodeView)
        assert code.document.lines[-1] == "# new" and code.cursor_row == 1
        assert app.query_one(StatusBar).text.endswith("of 3")


async def test_an_unchanged_file_is_left_alone(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        before = app.query_one(CodeView).document
        await app._check_for_changes()
        assert app.query_one(CodeView).document is before


async def test_a_deleted_file_stays_on_screen(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        (project / "src" / "app.py").unlink()
        await app._check_for_changes()
        assert app.query_one(CodeView).document.lines[0] == "def main():"


async def test_the_editor_result_is_shown_when_it_returns(project, tmp_path, monkeypatch):
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.setattr(SpycApp, "_run_editor", lambda self, command: change(project / "README.md", "# Changed\n"))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app.query_one(CodeView).document.lines == ("# Changed",)


async def test_capital_r_picks_up_new_files(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        write_files(project, {"src/new.py": "x = 1\n"})
        await pilot.press("R")
        await ready(pilot)
        assert app.overview.file_count == 4


async def test_r_toggles_a_rendered_markdown_view(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.query_one(MarkdownPane).display and not app.query_one(CodeView).display
        await pilot.press("r")
        await pilot.pause()
        assert app.query_one(CodeView).display and not app.query_one(MarkdownPane).display


async def test_r_does_nothing_for_a_file_that_is_not_markdown(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.query_one(CodeView).display and not app.query_one(MarkdownPane).display


async def test_opening_another_file_leaves_the_rendered_view(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        app.open_file("src/app.py")
        await pilot.pause()
        assert app.query_one(CodeView).display and not app.query_one(MarkdownPane).display


async def test_question_mark_opens_the_help_and_escape_closes_it(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_the_saved_theme_is_restored(project, tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.set("theme", "nord")
    app = SpycApp(project, None, store)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.theme == "nord"


async def test_a_theme_change_is_saved(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.theme = "textual-light"
        await pilot.pause()
    assert StateStore(tmp_path / "state.json").get("theme") == "textual-light"


async def test_an_unknown_saved_theme_is_ignored(project, tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.set("theme", "no-such-theme")
    app = SpycApp(project, None, store)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.theme != "no-such-theme"
