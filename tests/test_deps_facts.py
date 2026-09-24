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


import pytest

from spyc.deps.facts import ClassDef, FileFacts, Import, facts_from_json, facts_to_json

FACTS = FileFacts("com.acme", (ClassDef("A", 3), ClassDef("B", 9)),
                  (Import("x.Y"), Import("x", wildcard=True, static=True), Import("m", level=2, names=("a", "b"))),
                  frozenset({"Y", "Z"}), "java")


def test_facts_survive_a_round_trip_through_json_and_the_json_is_stable():
    data = facts_to_json(FACTS)
    assert facts_from_json(data) == FACTS
    assert facts_to_json(facts_from_json(data)) == data
    assert data["used"] == ["Y", "Z"]


@pytest.mark.parametrize("data", [{}, {"unit": 1}, {"unit": "", "classes": [[1]], "imports": [], "used": []},
                                  {"unit": "", "classes": [], "imports": [["a"]], "used": []}])
def test_facts_that_are_not_facts_raise_the_errors_the_cache_reader_handles(data):
    with pytest.raises((KeyError, ValueError, TypeError)):
        facts_from_json(data)


@pytest.mark.parametrize("data", [
    {"unit": "", "classes": [["B", "7"]], "imports": [], "used": [], "language": ""},
    {"unit": "", "classes": [[3, 7]], "imports": [], "used": [], "language": ""},
    {"unit": "", "classes": [], "imports": [[123, False, False, 0, []]], "used": [], "language": ""},
    {"unit": "", "classes": [], "imports": [["a", "yes", False, 0, []]], "used": [], "language": ""},
    {"unit": "", "classes": [], "imports": [], "used": [1], "language": ""}])
def test_facts_with_the_wrong_kinds_of_values_are_refused_not_carried_into_the_graph(data):
    with pytest.raises((TypeError, ValueError)):
        facts_from_json(data)


@pytest.mark.parametrize("data", [
    {"unit": "", "classes": [], "imports": [["a", False, False, "1", []]], "used": [], "language": ""},
    {"unit": "", "classes": [], "imports": [["a", False, False, 1, [3]]], "used": [], "language": ""},
    {"unit": "", "classes": [], "imports": [], "used": [], "language": 4},
    {"unit": "", "classes": [], "imports": [["a", False, False, 1]], "used": [], "language": ""}])
def test_the_new_fields_are_checked_too(data):
    with pytest.raises((TypeError, ValueError)):
        facts_from_json(data)
