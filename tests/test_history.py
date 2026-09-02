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


from spyc.history import JumpHistory, Place

A, B, C = Place("a.py", 10), Place("b.py", 1), Place("c.py", 1)


def test_there_is_nowhere_to_go_at_first():
    history = JumpHistory()
    history.navigate(None, A)
    assert history.back(A) is None and history.forward(A) is None


def test_back_returns_where_you_left_and_forward_where_you_were():
    history = JumpHistory()
    history.navigate(None, A)
    history.navigate(Place("a.py", 57), B)
    assert history.back(Place("b.py", 20)) == Place("a.py", 57)
    assert history.forward(Place("a.py", 60)) == Place("b.py", 20)


def test_navigating_after_going_back_drops_the_forward_places():
    history = JumpHistory()
    history.navigate(None, A)
    history.navigate(A, B)
    history.back(B)
    history.navigate(A, C)
    assert history.forward(C) is None
    assert history.back(C) == A


def test_jumps_inside_one_file_are_places_too():
    history = JumpHistory()
    history.navigate(None, Place("a.py", 1))
    history.navigate(Place("a.py", 57), Place("a.py", 10))
    assert history.back(Place("a.py", 10)) == Place("a.py", 57)


def test_going_to_the_place_you_are_at_adds_nothing():
    history = JumpHistory()
    history.navigate(None, A)
    history.navigate(A, A)
    assert history.back(A) is None


def test_the_oldest_places_are_dropped_past_the_limit():
    history = JumpHistory(limit=3)
    history.navigate(None, Place("0", 1))
    for number in range(1, 6):
        history.navigate(Place(str(number - 1), 1), Place(str(number), 1))
    assert history.back(Place("5", 1)) == Place("4", 1)
    assert history.back(Place("4", 1)) == Place("3", 1)
    assert history.back(Place("3", 1)) is None
