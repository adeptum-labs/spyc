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

import pytest
from textual.widgets import Markdown, Static

from fake_claude import install_claude, needs_sh, result, text_delta, tool_use
from repos import write_files
from spyc.app import SpycApp
from spyc.assist.cli import find_claude
from spyc.screens.explain import ExplainScreen
from spyc.screens.graph import GraphScreen
from spyc.screens.scope_menu import ScopeMenu
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from waiting import until

pytestmark = needs_sh
SIZE = (140, 40)
FILES = {
    "tools/one.py": "import two\n\nclass Tool:\n    def run(self):\n        pass\n\ndef helper():\n    pass\n",
    "tools/two.py": "x = 1\n",
    "src/a/A.java": "package com.acme.a;\nimport com.acme.b.B;\npublic class A { B b; }\n",
    "src/b/B.java": "package com.acme.b;\npublic class B {}\n",
}
ANSWER = (text_delta("The "), tool_use("Read", file_path="tools/one.py"), text_delta("A "), result("A **tool** collection."))


def make_app(tmp_path, monkeypatch, *, logged_in=True, **options):
    root = tmp_path / "proj"
    write_files(root, FILES)
    fake = install_claude(tmp_path / "bin", monkeypatch, auth=f'{{"loggedIn": {str(logged_in).lower()}}}', **({"stream": ANSWER} | options))
    monkeypatch.setattr("spyc.app.find_claude", find_claude)
    return SpycApp(root, None, StateStore(tmp_path / "state.json")), fake


async def ready(pilot, claude=True):
    app = pilot.app
    await until(pilot, lambda: app._graph is not None and (app._claude is not None) == claude)


async def ask_about_directory(pilot, directory="tools"):
    pilot.app._tree.reveal(directory)
    pilot.app._tree.focus()
    await pilot.pause()
    await pilot.press("a")


def body(app):
    return app.screen.query_one(Markdown).source


def status(app):
    return app.screen.query_one("#explain-status", Static).render().plain


async def answered(pilot):
    await until(pilot, lambda: isinstance(pilot.app.screen, ExplainScreen) and "tool" in body(pilot.app))


async def test_a_on_a_directory_shows_what_claude_answered(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await answered(pilot)
        assert body(app) == "A **tool** collection."
        assert "sonnet" in status(app)
        assert "directory `tools`" in fake.prompt and "- tools/one.py" in fake.prompt
        assert "Depends on: tools/two.py" not in fake.prompt and "Defines: class Tool (tools/one.py:3)" in fake.prompt


async def test_the_graph_facts_go_into_the_question(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app._tree.reveal("tools/one.py")
        app._tree.focus()
        await pilot.press("a")
        await answered(pilot)
        assert "Depends on: tools/two.py ×1" in fake.prompt


async def test_a_second_visit_is_answered_from_the_cache_without_asking_claude(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await answered(pilot)
        await pilot.press("escape")
        await until(pilot, lambda: not isinstance(app.screen, ExplainScreen))
        await pilot.press("a")
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and "cached" in status(app))
        assert "tool" in body(app) and "changed" not in status(app)
        assert fake.runs == 1


async def test_a_cache_is_kept_between_runs_of_spyc(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await answered(pilot)
    later = SpycApp(tmp_path / "proj", None, StateStore(tmp_path / "state.json"))
    async with later.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await until(pilot, lambda: isinstance(later.screen, ExplainScreen) and "cached" in status(later))
    assert fake.runs == 1


async def test_code_that_changed_since_the_answer_is_marked_and_r_asks_again(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await answered(pilot)
        await pilot.press("escape")
        (tmp_path / "proj" / "tools" / "two.py").write_text("x = 2\n")
        await pilot.press("a")
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and "code changed" in status(app))
        assert fake.runs == 1
        await pilot.press("r")
        await until(pilot, lambda: fake.runs == 2 and "changed" not in status(app) and "s" in status(app))
        await until(pilot, lambda: "sonnet ·" in status(app) and "cached" not in status(app))


async def test_a_does_nothing_when_claude_is_not_installed_or_not_logged_in(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch, logged_in=False)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot, claude=False)
        await ask_about_directory(pilot)
        await pilot.pause(0.3)
        assert not isinstance(app.screen, ExplainScreen) and fake.runs == 0


async def test_a_does_nothing_without_a_claude_on_the_path(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", "")
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot, claude=False)
        await ask_about_directory(pilot)
        await pilot.pause(0.3)
        assert not isinstance(app.screen, ExplainScreen)


async def test_escape_while_claude_works_stops_it_and_returns(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch, stream=(text_delta("x"),), pause=30)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and fake.runs == 1)
        await until(pilot, lambda: "sonnet" in status(app))
        await pilot.press("escape")
        await until(pilot, lambda: not isinstance(app.screen, ExplainScreen))

        def gone():
            try:
                os.kill(fake.pid, 0)
            except ProcessLookupError:
                return True
            return False

        await until(pilot, gone)


async def test_what_claude_says_before_reading_is_not_kept(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch, stream=(text_delta("Let me look."), tool_use("Read", file_path="tools/one.py"), text_delta("Second part."), ""), pause=5)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and "Second part." in body(app))
        assert "Let me look." not in body(app) and "Reading tools/one.py" in status(app)


async def test_a_failure_is_shown_with_the_message_and_not_kept(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch, stream=(result("Credit balance is too low", error=True),), status=1)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and "Credit balance is too low" in body(app))
        assert "failed" in status(app)
        await pilot.press("escape")
        await pilot.press("a")
        await until(pilot, lambda: fake.runs == 2)


async def test_control_characters_in_an_answer_are_made_harmless(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch, stream=(result("Bad \x1b]52;c;ZXZpbA==\x07 text"),))
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await ask_about_directory(pilot)
        await until(pilot, lambda: isinstance(app.screen, ExplainScreen) and "Bad" in body(app))
        assert "\x1b" not in body(app) and "\x07" not in body(app)


async def test_in_the_code_a_menu_offers_the_class_at_the_cursor_first(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("tools/one.py", 5)
        await until(pilot, lambda: app.query_one(CodeView).cursor_row == 4)
        await pilot.press("a")
        await until(pilot, lambda: isinstance(app.screen, ScopeMenu))
        assert [str(app.screen.query_one("OptionList").get_option_at_index(index).prompt) for index in range(3)] == [
            "class Tool", "file tools/one.py", "directory tools"]
        await pilot.press("enter")
        await answered(pilot)
        assert "class `Tool`" in fake.prompt and "`tools/one.py:3`" in fake.prompt


async def test_in_the_code_the_menu_can_be_left_with_escape(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("tools/one.py", 8)
        await until(pilot, lambda: app.query_one(CodeView).cursor_row == 7)
        await pilot.press("a")
        await until(pilot, lambda: isinstance(app.screen, ScopeMenu))
        await pilot.press("escape")
        await until(pilot, lambda: not isinstance(app.screen, ScopeMenu))
        assert fake.runs == 0


async def test_a_in_the_graph_asks_about_the_node_in_the_middle(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("src/a/A.java")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/a/A.java")
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("a")
        await answered(pilot)
        assert "package `com.acme.a`" in fake.prompt and "Depends on: com.acme.b ×1" in fake.prompt
        await pilot.press("escape")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))


async def test_a_is_not_offered_in_the_graph_without_claude(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch, logged_in=False)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot, claude=False)
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("a")
        await pilot.pause(0.3)
        assert isinstance(app.screen, GraphScreen)
