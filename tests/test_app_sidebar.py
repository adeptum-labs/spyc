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


from test_app import SIZE, make_app, ready

from spyc.app import MIN_MAIN_WIDTH, MIN_SIDEBAR_WIDTH, SIDEBAR_STEP, SIDEBAR_WIDTH, SpycApp
from spyc.state import StateStore
from spyc.widgets.file_tree import FileTree
from spyc.widgets.splitter import Splitter

MAX_SIDEBAR_WIDTH = SIZE[0] - MIN_MAIN_WIDTH - 1


def tree_width(app):
    return app.query_one(FileTree).outer_size.width


async def test_the_sidebar_starts_at_its_default_width(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert tree_width(app) == SIDEBAR_WIDTH


async def test_the_keys_widen_and_narrow_the_sidebar(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("greater_than_sign")
        assert tree_width(app) == SIDEBAR_WIDTH + SIDEBAR_STEP
        await pilot.press("less_than_sign", "less_than_sign")
        assert tree_width(app) == SIDEBAR_WIDTH - SIDEBAR_STEP


async def test_the_sidebar_stops_at_the_narrowest_and_widest_width(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press(*["less_than_sign"] * 40)
        assert tree_width(app) == MIN_SIDEBAR_WIDTH
        await pilot.press(*["greater_than_sign"] * 80)
        assert tree_width(app) == MAX_SIDEBAR_WIDTH


async def test_dragging_the_splitter_resizes_the_sidebar(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.mouse_down(Splitter)
        await pilot.hover(Splitter, offset=(20, 0))
        await pilot.mouse_up(Splitter)
        assert tree_width(app) == SIDEBAR_WIDTH + 20


async def test_a_splitter_not_pressed_does_not_resize_the_sidebar(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.hover(Splitter, offset=(20, 0))
        assert tree_width(app) == SIDEBAR_WIDTH


async def test_the_width_is_saved_and_restored(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("greater_than_sign")
    again = make_app(project, tmp_path)
    async with again.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert tree_width(again) == SIDEBAR_WIDTH + SIDEBAR_STEP


async def test_a_saved_width_too_wide_for_the_terminal_is_cut_down(project, tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.set("sidebar_width", 500)
    app = SpycApp(project, None, store)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        assert tree_width(app) == MAX_SIDEBAR_WIDTH


async def test_the_splitter_hides_with_the_tree(project, tmp_path):
    app = make_app(project, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("backslash")
        assert not app.query_one(Splitter).display
        await pilot.press("backslash")
        assert app.query_one(Splitter).display
