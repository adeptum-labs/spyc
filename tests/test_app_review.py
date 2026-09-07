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


import contextlib
import time

from textual.widgets import OptionList

import spyc.app
from repos import make_repo, write_files
from spyc.app import SpycApp
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from spyc.widgets.markdown_pane import MarkdownPane

SIZE = (140, 40)


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def top_level(app):
    return [str(node.label) for node in app.query_one(FileTree).root.children]


async def test_a_missing_editor_is_reported_not_fatal(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setenv("EDITOR", "no-such-editor-binary")
    monkeypatch.setattr(SpycApp, "suspend", lambda self: contextlib.nullcontext())
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
    assert any("no-such-editor-binary" in note for note in notes)


async def test_text_that_looks_like_markup_is_shown_as_typed(project, tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append((message, options)))
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/app.py")
        await pilot.pause()
        app._searched("tags[/]")
        app.open_file("nope[/].py")
    assert notes[0] == ("No matches for 'tags[/]'", {"severity": "warning", "markup": False})
    assert notes[1][1] == {"severity": "error", "markup": False}


async def test_a_stale_index_never_replaces_a_newer_one(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "repo", {"a.py": "x = 1\n", ".gitignore": "build/\n"})
    write_files(repo, {"build/out.o": ""})
    real = spyc.app.build_index

    def slow_when_ignored_files_are_hidden(root, show_ignored=False, limit=200_000):
        if not show_ignored:
            time.sleep(0.6)
        return real(root, show_ignored, limit)

    monkeypatch.setattr(spyc.app, "build_index", slow_when_ignored_files_are_hidden)
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("full_stop")
        await pilot.pause(1.2)
        assert "build" in top_level(app)


async def test_tab_reaches_the_key_files_on_the_overview_and_comes_back(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert app.query_one(FileTree).has_focus
        await pilot.press("tab")
        assert app.query_one(OptionList).has_focus
        await pilot.press("tab")
        assert app.query_one(FileTree).has_focus


async def test_tab_leaves_the_rendered_markdown(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.query_one(MarkdownPane).has_focus
        await pilot.press("tab")
        assert app.query_one(FileTree).has_focus


async def test_a_huge_markdown_file_is_left_as_source(project, tmp_path, monkeypatch):
    write_files(project, {"README.md": "# Demo\n" + "text " * 50})
    monkeypatch.setattr(spyc.app, "MARKDOWN_LIMIT", 100)
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("README.md")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.query_one(CodeView).display and not app.query_one(MarkdownPane).display
