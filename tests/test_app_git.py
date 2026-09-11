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
import time

from textual import events
from textual.widgets import OptionList

import spyc.app
from spyc.app import SpycApp
from spyc.git.repository import Git
from repos import git, write_files
from spyc.screens.changes import ChangesScreen
from spyc.screens.log import LogScreen
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.diff_view import DiffView
from spyc.widgets.file_tree import FileTree

SIZE = (140, 40)


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def top_level(app):
    return [str(node.label) for node in app.query_one(FileTree).root.children]


async def test_changed_files_are_marked_in_the_tree_from_the_start(git_repo, tmp_path):
    (git_repo / "README.md").write_text("changed\n")
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert "README.md M" in top_level(app)
        assert "src M" not in top_level(app)


async def test_a_project_without_git_has_no_marks_and_stops_asking(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert top_level(app) == ["src", "pom.xml", "README.md"]
        assert app.git_enabled is False


async def test_capital_r_reads_the_state_again(git_repo, tmp_path):
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        (git_repo / "README.md").write_text("changed\n")
        await pilot.press("R")
        await ready(pilot)
        assert "README.md M" in top_level(app)


async def test_the_marks_follow_the_editor(git_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.setattr(SpycApp, "_run_editor", lambda self, command: (git_repo / "README.md").write_text("edited\n"))
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("e")
        await ready(pilot)
        assert "README.md M" in top_level(app)


async def test_the_marks_are_refreshed_when_the_window_regains_focus(git_repo, tmp_path):
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        (git_repo / "README.md").write_text("changed\n")
        app.post_message(events.AppFocus())
        await ready(pilot)
        assert "README.md M" in top_level(app)


async def test_the_marks_are_refreshed_on_a_timer(git_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(spyc.app, "GIT_INTERVAL", 0.2)
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        (git_repo / "README.md").write_text("changed\n")
        await pilot.pause(1.0)
        await ready(pilot)
        assert "README.md M" in top_level(app)


async def test_changed_lines_are_marked_in_the_open_file(git_repo, tmp_path):
    (git_repo / "README.md").write_text("# Project\n\nA test project.\nMore\n")
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        code = app.query_one(CodeView)
        assert "▎" in code.render_line(3).text and "▎" not in code.render_line(0).text


async def test_a_new_untracked_file_is_marked_as_added_all_through(git_repo, tmp_path):
    write_files(git_repo, {"new.py": "a = 1\nb = 2\n"})
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("new.py")
        await ready(pilot)
        code = app.query_one(CodeView)
        assert "▎" in code.render_line(0).text and "▎" in code.render_line(1).text


async def test_a_project_without_git_has_no_change_column(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await ready(pilot)
        assert app.query_one(CodeView).render_line(0).text.startswith("   1 def main")


async def test_the_marks_follow_a_reload_of_the_file(git_repo, tmp_path):
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        code = app.query_one(CodeView)
        assert "▎" not in code.render_line(2).text
        (git_repo / "README.md").write_text("# Project\n\nchanged\n")
        os.utime(git_repo / "README.md", (time.time() + 10, time.time() + 10))
        await app._check_for_changes()
        await ready(pilot)
        assert "▎" in code.render_line(2).text


async def test_l_opens_the_log_and_enter_on_a_diff_line_opens_that_file(git_repo, tmp_path):
    (git_repo / "README.md").write_text("# Project\n\nA test project.\nMore\n")
    git(git_repo, "commit", "-qam", "Add a line")
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("l")
        await pilot.pause(0.8)
        assert isinstance(app.screen, LogScreen)
        await pilot.press("enter")
        rows = app.screen.query_one(DiffView).rows
        add = next(index for index, row in enumerate(rows) if row.kind == "add")
        await pilot.press(*["down"] * add, "enter")
        await pilot.pause(0.3)
        code = app.query_one(CodeView)
        assert code.display_path == "README.md" and code.cursor_row == 3


async def test_capital_l_shows_the_history_of_the_open_file(git_repo, tmp_path):
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("L")
        await pilot.pause(0.5)
        assert isinstance(app.screen, LogScreen) and app.screen.sub_title == "Log of README.md"


async def test_capital_l_without_an_open_file_says_what_is_needed(git_repo, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("L")
        await pilot.pause()
        assert not isinstance(app.screen, LogScreen) and notes == ["Open a file to see its history"]


async def test_g_opens_the_changes(git_repo, tmp_path):
    (git_repo / "README.md").write_text("# Project\n\nchanged\n")
    write_files(git_repo, {"new.py": "x = 1\n"})
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("g")
        await pilot.pause(0.8)
        assert isinstance(app.screen, ChangesScreen)
        titles = {row.text.split("  ")[0] for row in app.screen.query_one(DiffView).rows if row.kind == "file"}
        assert titles == {"modified README.md", "added new.py"}


async def test_the_git_keys_explain_themselves_outside_a_repository(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("l", "g")
        await pilot.pause()
        assert notes == ["Not a git repository", "Not a git repository"]
        assert len(app.screen_stack) == 1


async def test_b_shows_and_hides_who_changed_each_line(git_repo, tmp_path):
    first = Git(git_repo).log()[0].short
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        code = app.query_one(CodeView)
        await pilot.press("b")
        await ready(pilot)
        assert code.render_line(0).text.startswith(first)
        await pilot.press("b")
        await pilot.pause()
        assert code.blame is None and code.render_line(0).text.startswith("   1   # Project")


async def test_the_blame_column_follows_the_files_that_are_opened(git_repo, tmp_path):
    first = Git(git_repo).log()[0].short
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        await pilot.press("b")
        await ready(pilot)
        app.open_file("pyproject.toml")
        await ready(pilot)
        assert app.query_one(CodeView).render_line(0).text.startswith(first)


async def test_enter_on_a_blamed_line_opens_that_commit_in_the_log(git_repo, tmp_path):
    first = Git(git_repo).log()[0]
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        await pilot.press("b")
        await ready(pilot)
        await pilot.press("enter")
        await pilot.pause(0.8)
        assert isinstance(app.screen, LogScreen)
        assert app.screen.query_one(OptionList).highlighted == 0
        assert first.short in str(app.screen.query_one(OptionList).get_option_at_index(0).prompt)


async def test_enter_on_an_uncommitted_line_opens_the_changes(git_repo, tmp_path):
    (git_repo / "README.md").write_text("# Project\n\nA test project.\nMore\n")
    app = make_app(git_repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await ready(pilot)
        await pilot.press("b")
        await ready(pilot)
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause(0.8)
        assert isinstance(app.screen, ChangesScreen)


async def test_b_outside_a_repository_says_so(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        assert notes == ["Not a git repository"] and app.query_one(CodeView).blame is None
