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


from repos import write_files
from spyc.app import SpycApp
from spyc.deps.graph import DependencyGraph
from spyc.screens.graph import GraphScreen
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.graph_view import GraphView
from waiting import until

SIZE = (140, 40)
JAVA = {
    "src/a/A.java": "package com.acme.a;\nimport com.acme.b.B;\npublic class A { B b; }\n",
    "src/b/B.java": "package com.acme.b;\npublic class B {}\n",
}


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def graph_ready(pilot):
    await until(pilot, lambda: pilot.app._graph is not None)


def header(app):
    return app.screen.query_one("#graph-header").render().plain


def graph_text(app):
    return "\n".join(line.plain for line in app.screen.query_one(GraphView).drawing.lines)


async def test_g_shows_the_packages_of_a_java_project_around_the_open_file(tmp_path):
    write_files(tmp_path / "proj", JAVA)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        app.open_file("src/a/A.java")
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/a/A.java")
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert header(app).startswith("package com.acme.a · 1 out · 0 in")


async def test_o_in_the_graph_opens_the_file_of_a_class_at_its_line_and_escape_goes_back(tmp_path):
    write_files(tmp_path / "proj", JAVA)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("escape")
        await until(pilot, lambda: not isinstance(app.screen, GraphScreen))
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("right_square_bracket", "right_square_bracket", "o")
        await until(pilot, lambda: not isinstance(app.screen, GraphScreen))
        await until(pilot, lambda: app.query_one(CodeView).display_path == "src/a/A.java")
        await until(pilot, lambda: app.query_one(CodeView).cursor_row == 2)


async def test_g_before_the_pass_is_done_shows_the_progress_and_the_graph_arrives_by_itself(tmp_path, monkeypatch):
    write_files(tmp_path / "proj", JAVA)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        graph, app._graph = app._graph, None
        monkeypatch.setattr(app, "_symbol_progress", lambda: "indexing 1/2")
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert "Reading imports (indexing 1/2)" in graph_text(app)
        app._graph_ready(app._index_generation, graph)
        await until(pilot, lambda: "com.acme.b" in graph_text(app))


async def test_a_project_without_java_or_kotlin_gets_an_empty_graph_and_a_message(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        assert app._graph.empty
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert "No dependencies found" in graph_text(app)


async def test_a_graph_from_an_older_pass_is_dropped(tmp_path):
    write_files(tmp_path / "proj", JAVA)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        current = app._graph
        app._graph_ready(app._index_generation - 1, DependencyGraph({}))
        assert app._graph is current


async def test_r_builds_the_graph_again_after_a_file_is_added(tmp_path):
    write_files(tmp_path / "proj", JAVA)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await graph_ready(pilot)
        assert len(app._graph.nodes("unit")) == 2
        write_files(tmp_path / "proj", {"src/c/C.java": "package com.acme.c;\nimport com.acme.a.A;\nclass C {}\n"})
        await pilot.press("R")
        await until(pilot, lambda: len(app._graph.nodes("unit")) == 3)


def notes_of(monkeypatch):
    notes = []
    monkeypatch.setattr(SpycApp, "notify", lambda self, message, **options: notes.append(message))
    return notes


async def test_an_error_while_indexing_is_told_to_the_user_and_shown_in_the_graph_screen(tmp_path, monkeypatch):
    def broken(facts, stop=lambda: False):
        raise RuntimeError("boom \x1b[2J")

    write_files(tmp_path / "proj", JAVA)
    monkeypatch.setattr("spyc.app.DependencyGraph", broken)
    notes = notes_of(monkeypatch)
    app = make_app(tmp_path / "proj", tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await until(pilot, lambda: notes)
        assert notes == ["Could not index the project: boom ␛[2J"]
        await pilot.press("G")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert "Could not index the project" in graph_text(app) and "No dependencies found" not in graph_text(app)


async def test_a_graph_build_is_cut_short_when_the_app_is_left(tmp_path, monkeypatch):
    import time
    seen = []

    def slow(facts, stop=lambda: False):
        deadline = time.monotonic() + 5
        while not stop() and time.monotonic() < deadline:
            time.sleep(0.01)
        seen.append(stop())
        from spyc.deps.graph import Stopped
        raise Stopped

    write_files(tmp_path / "proj", JAVA)
    monkeypatch.setattr("spyc.app.DependencyGraph", slow)
    async with make_app(tmp_path / "proj", tmp_path).run_test(size=SIZE) as pilot:
        await pilot.pause(0.5)
        assert seen == []
    deadline = time.monotonic() + 5
    while not seen and time.monotonic() < deadline:
        time.sleep(0.02)
    assert seen == [True]
