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



import time

from spyc.deps.impact import reached, reversed_edges

EDGES = {"web": {"order": 1}, "order": {"model": 2, "billing": 1}, "billing": {"order": 1}, "model": {}}


def test_what_a_node_depends_on_is_everything_it_reaches():
    assert reached(EDGES, "web") == {"order", "model", "billing"}
    assert reached(EDGES, "model") == frozenset()


def test_what_depends_on_a_node_is_everything_that_reaches_it():
    assert reached(reversed_edges(EDGES), "model") == {"order", "billing", "web"}
    assert reached(reversed_edges(EDGES), "web") == frozenset()


def test_the_members_of_a_cycle_reach_each_other_and_themselves():
    assert reached(EDGES, "order") == {"model", "billing", "order"}


def test_a_long_chain_is_walked_without_deep_recursion():
    chain = {number: {number + 1: 1} for number in range(5000)}
    started = time.perf_counter()
    assert len(reached(chain, 0)) == 5000
    assert len(reached(reversed_edges(chain), 5000)) == 5000
    assert time.perf_counter() - started < 2
