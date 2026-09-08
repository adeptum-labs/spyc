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


from textual import events

import spyc.app
from spyc.app import SpycApp
from spyc.state import StateStore
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
