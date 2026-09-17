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
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from spyc.widgets.status_bar import StatusBar
from waiting import until

SIZE = (140, 40)
LCOV = "SF:src/app.py\nDA:1,1\nDA:2,0\nend_of_record\n"


def make_app(root, tmp_path, coverage_files=()):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"), coverage_files=coverage_files)


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def opened(pilot, path="src/app.py"):
    await ready(pilot)
    pilot.app.open_file(path)
    await until(pilot, lambda: pilot.app.query_one(CodeView).display_path == path)


def marks(app):
    return [app.query_one(CodeView).render_line(row).text[5:7] for row in range(2)]


async def test_a_report_found_in_the_project_marks_the_lines_and_says_the_share_in_the_status(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        assert marks(app) == ["● ", "○ "]
        await until(pilot, lambda: "coverage 50%" in app.query_one(StatusBar).text)


async def test_c_hides_and_shows_the_marks_and_remembers_the_choice(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        await pilot.press("c")
        assert app.query_one(CodeView).coverage is None and app.store.get("coverage") is False
        await until(pilot, lambda: "coverage 50%" in app.query_one(StatusBar).text)
        await pilot.press("c")
        assert marks(app) == ["● ", "○ "] and app.store.get("coverage") is True


async def test_a_choice_to_hide_the_marks_is_kept_for_the_next_run(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    StateStore(tmp_path / "state.json").set("coverage", False)
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        assert app.query_one(CodeView).coverage is None


async def test_a_file_the_report_does_not_know_keeps_an_empty_column_so_the_text_does_not_move(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        app.open_file("README.md")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "README.md")
        assert app.query_one(CodeView).coverage == {}


async def test_c_says_what_to_do_when_there_is_no_report(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        await pilot.press("c")
        assert notes == ["No coverage report found; run the tests with coverage or start spyc with --coverage FILE"]


async def test_a_report_given_on_the_command_line_is_used_wherever_it_is(project, tmp_path):
    write_files(tmp_path, {"elsewhere/cov.dat": LCOV})
    app = make_app(project, tmp_path, [tmp_path / "elsewhere" / "cov.dat"])
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        assert marks(app) == ["● ", "○ "]


async def test_a_report_given_on_the_command_line_that_cannot_be_read_is_said_so(project, tmp_path, monkeypatch):
    write_files(tmp_path, {"bad.dat": "not a report"})
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path, [tmp_path / "bad.dat"])
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        assert notes == ["Coverage report skipped, bad.dat: Not a coverage report"]


async def test_a_file_changed_after_its_report_is_called_stale(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    os.utime(project / "coverage" / "lcov.info", (1000, 1000))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await opened(pilot)
        await until(pilot, lambda: "coverage 50% (stale)" in app.query_one(StatusBar).text)


def tree_labels(app):
    return [str(node.label) for node in app.query_one(FileTree).root.children]


async def test_the_tree_and_the_overview_give_the_shares_and_c_takes_the_tree_ones_away(project, tmp_path):
    write_files(project, {"coverage/lcov.info": LCOV})
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert "src 50%" in tree_labels(app)
        assert app.query_one("#coverage").render().plain.startswith("Coverage 50% · 1 of 2 lines · LCOV")
        await pilot.press("c")
        await pilot.pause()
        assert "src" in tree_labels(app) and app.query_one("#coverage").display
